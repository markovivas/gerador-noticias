"""Orquestra a arte no Affinity: copia o modelo, edita, salva e exporta o PNG."""
import json
import re
import shutil
from pathlib import Path

from mcp_affinity import AffinityMCPClient

CAMADAS_TEXTO = ("TITULO", "SUB-TITULO", "DONO NA IMAGEM")


def nome_base(id_noticia, data_br):
    """'1523', '07/09/2026' -> 'noticia-1523-07-09-2026'."""
    dia, mes, ano = [p.zfill(2) for p in data_br.strip().split("/")]
    return f"noticia-{id_noticia.strip()}-{dia}-{mes}-{ano}"


def preparar_projeto(caminho_modelo, dir_projetos, base):
    """Copia o modelo sem alterá-lo. Retorna o caminho da cópia."""
    dir_projetos.mkdir(parents=True, exist_ok=True)
    antes = caminho_modelo.stat()
    destino = dir_projetos / f"{base}.af"
    if destino.exists():
        destino.unlink()  # recomeça do modelo limpo a cada geração
    shutil.copy2(caminho_modelo, destino)
    depois = caminho_modelo.stat()
    assert (antes.st_size, antes.st_mtime) == (depois.st_size, depois.st_mtime), \
        "Modelo original foi tocado na cópia"
    return destino


def montar_js(caminho_projeto, caminho_imagem, caminho_png, titulo, subtitulo, credito):
    """Monta o script executado dentro do Affinity (etapas com log)."""
    p = lambda valor: json.dumps(str(valor))
    return f"""
const {{ Document, FileExportOptions, FileExportArea }} = require('/document');
const {{ Selection, TextSelection }} = require('/selections');
const {{ DocumentCommand, AddChildNodesCommandBuilder }} = require('/commands');
const {{ ImageNodeDefinition }} = require('/nodes');
const {{ Bitmap }} = require('/rasterobject');
const {{ RasterFormat }} = require('affinity:raster');
const {{ NodeChildType, NodeMoveType }} = require('affinity:dom');
const {{ Transform }} = require('/geometry');
const {{ EnumerationResult }} = require('affinity:common');

const doc = Document.load({p(str(caminho_projeto))});
console.log("UUID=" + doc.sessionUuid);
console.log("ETAPA=carregado wPx=" + doc.widthPixels + " hPx=" + doc.heightPixels);

function findByDesc(desc) {{
  for (const l of doc.layers.all) {{
    try {{ if (l.descriptionInterface && l.descriptionInterface.userDescription === desc) return l; }} catch(_){{}}
  }}
  return null;
}}
function setAllText(desc, txt) {{
  const node = findByDesc(desc);
  if (!node) throw new Error("Camada ausente: " + desc);
  const range = node.storyInterface.storyRange;
  const sel = Selection.create(doc, node);
  sel.addSubSelectionForNode(node, TextSelection.create([{{begin: range.begin, end: range.end}}]));
  doc.executeCommand(DocumentCommand.createSetText(sel, txt));
  console.log("ETAPA=texto " + desc);
}}
setAllText("TITULO", {p(titulo)});
setAllText("SUB-TITULO", {p(subtitulo)});
setAllText("DONO NA IMAGEM", {p(credito)});

const foto = findByDesc("FOTO");
if (!foto) throw new Error("Camada FOTO ausente");
const caixa = foto.spreadVisibleBox;
const bm = Bitmap.loadFromFile({p(str(caminho_imagem))});
console.log("ETAPA=bitmap " + bm.width + "x" + bm.height);
const def = ImageNodeDefinition.create(RasterFormat.RGBA8);
def.bitmap = bm;
def.userDescription = "FOTO_NOVA";
const builder = AddChildNodesCommandBuilder.create();
builder.addImageNode(def);
builder.setInsertionTarget(foto.parent);
doc.executeCommand(builder.createCommand(false, NodeChildType.Main));
let nova = findByDesc("FOTO_NOVA");
if (!nova) throw new Error("Falha ao inserir imagem");
// Cobertura proporcional: preenche a caixa sem deformar.
const s = Math.max(caixa.width / bm.width, caixa.height / bm.height);
const tx = (caixa.x + caixa.width / 2) - (bm.width * s) / 2;
const ty = (caixa.y + caixa.height / 2) - (bm.height * s) / 2;
const xf = new Transform();
xf.data["0"] = s; xf.data["1"] = 0; xf.data["2"] = tx;
xf.data["3"] = 0; xf.data["4"] = s; xf.data["5"] = ty;
doc.executeCommand(DocumentCommand.createTransform(Selection.create(doc, nova), xf));
console.log("ETAPA=foto-posicionada");
// Gradiente de volta para cima da foto (ordem original).
let grad = null;
for (const l of doc.layers.all) {{
  try {{ if (l.descriptionInterface && l.descriptionInterface.userDescription === "Gradient Fill 1") grad = l; }} catch(_){{}}
}}
if (!grad) throw new Error("Gradient Fill 1 ausente");
doc.executeCommand(DocumentCommand.createMoveNodes(
  Selection.create(doc, nova), grad, NodeMoveType.Before, NodeChildType.Main));
doc.selection = Selection.create(doc, foto);
doc.executeCommand(DocumentCommand.createDeleteSelection(doc.selection));
nova.userDescription = "FOTO";
console.log("ETAPA=foto-trocada");

doc.save();
console.log("ETAPA=salvo " + doc.path);
const opts = FileExportOptions.createWithPresetName("PNG");
const area = FileExportArea.createForWholeDocument();
const rec = doc.export({p(str(caminho_png))}, opts, area, null);
rec.enumerate(r => {{ console.log("ETAPA=export success=" + r.isSuccess); return EnumerationResult.Continue; }});
console.log("FINAL DONE wPx=" + doc.widthPixels + " hPx=" + doc.heightPixels);
"""


def gerar_arte(caminho_modelo, dir_projetos, dir_exports, caminho_imagem,
               id_noticia, data_br, titulo, subtitulo, credito):
    """Executa o fluxo completo e retorna dict com log, uuid, png e preview."""
    base = nome_base(id_noticia, data_br)
    projeto = preparar_projeto(caminho_modelo, dir_projetos, base)
    png = dir_exports / f"{base}.png"
    dir_exports.mkdir(parents=True, exist_ok=True)

    js = montar_js(projeto, caminho_imagem, png, titulo, subtitulo, credito)
    cliente = AffinityMCPClient()
    try:
        log = cliente.executar_js(js, timeout=240)
    finally:
        cliente.fechar()

    achado = re.search(r"UUID=([A-F0-9\-]+)", log)
    uuid = achado.group(1) if achado else ""
    if "FINAL DONE" not in log or not png.exists():
        raise RuntimeError(f"Falha na arte. Log:\n{log}")

    cliente2 = AffinityMCPClient()
    try:
        preview_b64 = cliente2.renderizar_spread(uuid, 0) if uuid else ""
    except Exception:
        preview_b64 = ""
    finally:
        cliente2.fechar()

    return {"base": base, "projeto": str(projeto), "png": str(png),
            "uuid": uuid, "log": log, "preview_b64": preview_b64}
