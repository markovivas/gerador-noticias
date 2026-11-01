"""Orquestra a arte no PhotoCraft: edita o modelo PSD, salva o projeto e exporta o PNG."""
import base64
import json
import os
import subprocess
from pathlib import Path

PHOTOCRAFT_BIN = os.environ.get(
    "PHOTOCRAFT_BIN",
    r"C:\Program Files\ArtCraft\PhotoCraft\photocraft-cli.exe",
)


def nome_base(id_noticia, data_br):
    """'1523', '07/09/2026' -> 'noticia-1523-07-09-2026'."""
    partes = data_br.strip().split("/")
    if len(partes) != 3:
        raise ValueError("Data deve estar no formato DD/MM/AAAA")
    dia, mes, ano = [p.zfill(2) for p in partes]
    return f"noticia-{id_noticia.strip()}-{dia}-{mes}-{ano}"


def verificar_photocraft():
    """Valida se o executável do PhotoCraft CLI existe."""
    caminho = Path(PHOTOCRAFT_BIN)
    if not caminho.is_file():
        raise RuntimeError(
            f"PhotoCraft CLI não encontrado em '{PHOTOCRAFT_BIN}'. "
            "Verifique a instalação ou configure a variável PHOTOCRAFT_BIN."
        )
    return caminho


def gerar_arte(
    caminho_modelo: Path,
    dir_projetos: Path,
    dir_exports: Path,
    caminho_imagem: Path,
    id_noticia: str,
    data_br: str,
    titulo: str,
    subtitulo: str,
    credito: str,
):
    """Executa a substituição das camadas no PhotoCraft e exporta o PNG.

    Camadas editadas no PSD:
      - FOTO: Substituição do conteúdo do Smart Object pela nova imagem.
      - TITULO: Atualização da camada de texto do título.
      - SUB-TITULO: Atualização da camada de texto do subtítulo.
      - CREDITO: Atualização da camada de texto do crédito da foto.
    """
    bin_pc = verificar_photocraft()

    if not caminho_modelo.exists():
        raise FileNotFoundError(f"Arquivo de modelo não encontrado: {caminho_modelo}")
    if not caminho_imagem.exists():
        raise FileNotFoundError(f"Arquivo de imagem não encontrado: {caminho_imagem}")

    base = nome_base(id_noticia, data_br)
    dir_projetos.mkdir(parents=True, exist_ok=True)
    dir_exports.mkdir(parents=True, exist_ok=True)

    projeto_psd = dir_projetos / f"{base}.psd"
    export_png = dir_exports / f"{base}.png"

    # Se já existirem versões anteriores desse ID/data, remove para recriar limpo
    if projeto_psd.exists():
        projeto_psd.unlink()
    if export_png.exists():
        export_png.unlink()

    # 1. Edição do modelo no PhotoCraft: troca a foto e os textos
    cmd_run = [
        str(bin_pc),
        "run",
        str(caminho_modelo.resolve()),
        "--cmd", "layer.select", "--params", json.dumps({"name": "FOTO"}),
        "--cmd", "layer.smartObjects.replaceContents", "--params", json.dumps({"path": str(caminho_imagem.resolve())}),
        "--cmd", "layer.select", "--params", json.dumps({"name": "TITULO"}),
        "--cmd", "type.edit", "--params", json.dumps({"text": titulo}),
        "--cmd", "layer.select", "--params", json.dumps({"name": "SUB-TITULO"}),
        "--cmd", "type.edit", "--params", json.dumps({"text": subtitulo}),
        "--cmd", "layer.select", "--params", json.dumps({"name": "CREDITO"}),
        "--cmd", "type.edit", "--params", json.dumps({"text": credito}),
        "--out", str(projeto_psd.resolve()),
    ]

    proc_run = subprocess.run(
        cmd_run,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=120,
    )

    log = f"[PHOTOCRAFT RUN STDOUT]\n{proc_run.stdout}\n[PHOTOCRAFT RUN STDERR]\n{proc_run.stderr}\n"

    if proc_run.returncode != 0 or not projeto_psd.exists():
        raise RuntimeError(
            f"Falha ao gerar o arquivo PSD no PhotoCraft (código {proc_run.returncode}):\n{proc_run.stderr or proc_run.stdout}"
        )

    # 2. Conversão direta do PSD para PNG 1080x1350
    cmd_conv = [
        str(bin_pc),
        "convert",
        str(projeto_psd.resolve()),
        str(export_png.resolve()),
    ]

    proc_conv = subprocess.run(
        cmd_conv,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=60,
    )

    log += f"[PHOTOCRAFT CONVERT STDOUT]\n{proc_conv.stdout}\n[PHOTOCRAFT CONVERT STDERR]\n{proc_conv.stderr}\n"

    if proc_conv.returncode != 0 or not export_png.exists():
        raise RuntimeError(
            f"Falha ao exportar PNG no PhotoCraft (código {proc_conv.returncode}):\n{proc_conv.stderr or proc_conv.stdout}"
        )

    # 3. Gera prévia em base64 a partir do PNG gerado
    try:
        preview_b64 = base64.b64encode(export_png.read_bytes()).decode("ascii")
    except Exception:
        preview_b64 = ""

    return {
        "base": base,
        "projeto": str(projeto_psd),
        "png": str(export_png),
        "preview_b64": preview_b64,
        "log": log,
    }
