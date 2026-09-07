"""Gerador de Notícias: texto (Instagram + jornalístico) + PNG via Affinity.

Entrada: informações/texto + uma imagem.
Saída: arquivo Instagram (.md), arquivo jornalístico (.md) e PNG da arte.
"""
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

import arte
import texto

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB

BASE = Path(app.root_path)  # tudo vive dentro de gerador-noticias/
MODELO = BASE / "modelos" / "capa_noticia.af"
DIR_IMAGENS = BASE / "imagens"
DIR_PROJETOS = BASE / "projetos"
DIR_EXPORTS = BASE / "exports"
DIR_NOTICIAS = BASE / "noticias"
EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png"}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/gerar", methods=["POST"])
def gerar():
    noticia = (request.form.get("noticia") or "").strip()
    id_noticia = (request.form.get("id_noticia") or "").strip()
    data_br = (request.form.get("data") or "").strip() or date.today().strftime("%d/%m/%Y")
    credito = (request.form.get("credito") or "").strip()
    provedor = (request.form.get("provedor") or texto.PROVEDOR_PADRAO).strip()
    arquivo = request.files.get("imagem")

    if not noticia:
        return jsonify({"error": "Cole as informações/texto da notícia."}), 400
    if not id_noticia:
        return jsonify({"error": "Informe o ID da notícia."}), 400
    try:
        base = arte.nome_base(id_noticia, data_br)
    except (ValueError, IndexError, AttributeError):
        return jsonify({"error": "Data inválida. Use DD/MM/AAAA."}), 400
    if arquivo is None or not arquivo.filename:
        return jsonify({"error": "Envie uma imagem (JPG ou PNG)."}), 400
    extensao = Path(arquivo.filename).suffix.lower()
    if extensao not in EXTENSOES_IMAGEM:
        return jsonify({"error": "Imagem deve ser JPG ou PNG."}), 400
    if not MODELO.exists():
        return jsonify({"error": f"Modelo não encontrado: {MODELO}"}), 500

    # 1. Imagem: salva uma cópia nova em imagens/ (originais nunca são alteradas).
    DIR_IMAGENS.mkdir(parents=True, exist_ok=True)
    caminho_imagem = DIR_IMAGENS / f"{base}{extensao}"
    arquivo.save(caminho_imagem)

    # 2. Textos via provedor configurado (OpenCode ou Ollama).
    try:
        conteudo = texto.processar_noticia(noticia, credito, provedor)
    except Exception as erro:
        return jsonify({"error": f"Falha no provedor '{provedor}': {erro}"}), 502

    # 3. Arquivos de texto.
    DIR_NOTICIAS.mkdir(exist_ok=True)
    slug = texto.nome_base_unico(DIR_NOTICIAS, texto.slugify_text(conteudo["titulo_arte"] or base))
    arq_insta = DIR_NOTICIAS / f"{slug}_instagram.md"
    arq_jornal = DIR_NOTICIAS / f"{slug}_jornalistico.md"
    arq_insta.write_text(
        f"TITULO: {conteudo['titulo_arte']}\n\nLEGENDA:\n{conteudo['instagram']}",
        encoding="utf-8",
    )
    meta = " ".join(conteudo["jornalistico"].split())[:155]
    arq_jornal.write_text(
        f"Titulo: {conteudo['titulo_arte']}\nSlug: {slug}\nMeta descricao: {meta}\n\n"
        f"Conteudo:\n\n{conteudo['jornalistico']}",
        encoding="utf-8",
    )

    # 4. Arte no Affinity (pode levar 1-2 min).
    try:
        resultado_arte = arte.gerar_arte(
            MODELO, DIR_PROJETOS, DIR_EXPORTS, caminho_imagem,
            id_noticia, data_br,
            conteudo["titulo_arte"], conteudo["subtitulo"], conteudo["credito"],
        )
    except Exception as erro:
        return jsonify({"error": f"Falha na arte: {erro}"}), 500

    return jsonify({
        "instagram": conteudo["instagram"],
        "jornalistico": conteudo["jornalistico"],
        "titulo_arte": conteudo["titulo_arte"],
        "subtitulo": conteudo["subtitulo"],
        "credito": conteudo["credito"],
        "provedor": provedor,
        "preview_b64": resultado_arte["preview_b64"],
        "arquivos": {
            "instagram_md": arq_insta.name,
            "jornalistico_md": arq_jornal.name,
            "projeto_af": Path(resultado_arte["projeto"]).name,
            "png": Path(resultado_arte["png"]).name,
        },
    })


if __name__ == "__main__":
    app.run(debug=True)
