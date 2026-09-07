"""Geração de textos via Ollama + derivação dos textos da arte.

Fluxo:
  noticia (texto livre)
    -> Ollama devolve 3 blocos: [INSTAGRAM], [JORNALISTICO], [ARTE]
    -> daqui saem os 2 arquivos de texto + TITULO/SUBTITULO/CREDITO da arte.
"""
import os
import re
import subprocess
import tempfile
import unicodedata

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:e2b"
OLLAMA_CONNECT_TIMEOUT = 10
OLLAMA_READ_TIMEOUT = 600

# Provedor de texto: "opencode" (padrão, via `opencode run`) ou "ollama".
PROVEDOR_PADRAO = os.environ.get("GERADOR_PROVEDOR", "opencode")
OPENCODE_BIN = os.environ.get("GERADOR_OPENCODE_BIN", "opencode")
OPENCODE_MODEL = os.environ.get("GERADOR_MODEL", "")  # vazio = modelo padrão do OpenCode
OPENCODE_TIMEOUT = int(os.environ.get("GERADOR_OPENCODE_TIMEOUT", "300"))

SITE_URL = "https://terradorei.com.br/"
DEFAULT_INSTAGRAM_HASHTAGS = "#noticias #terradorei #informacao"
DEFAULT_JORNALISTICO_TAGS = "noticias, atualidade, informacao"

PROMPT_MODELO = """
Voce e um gerador de conteudo profissional.
Responda seguindo ESTRITAMENTE o formato abaixo, sem introducoes ou conclusoes.
Use exatamente as etiquetas indicadas:

[INSTAGRAM]
Resuma o texto de forma clara e objetiva. Comece com um paragrafo curto
contextualizando a noticia e apresente os principais pontos em topicos com
emoticons. Linguagem simples e jornalistica, sem opinioes nem dados novos.
Ao final, adicione:
SAIBA MAIS: https://terradorei.com.br/
E crie hashtags relevantes.

[JORNALISTICO]
Titulo: crie um titulo curto e atrativo.
Reescreva o texto de forma clara, objetiva e jornalistica, em texto corrido
com inicio, desenvolvimento e conclusao, preservando todas as informacoes.
Ao final, inclua:
Tags: exatamente 3 tags, mesma linha, separadas por virgula.

[ARTE]
TITULO: no maximo 3 palavras, representando o assunto principal.
SUBTITULO: no maximo 18 palavras, resumindo a informacao mais importante.
CREDITO: nome principal do autor da foto, ou vazio se desconhecido.

NOTICIA:
{noticia}
"""


def slugify_text(text):
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_text.lower()).strip("_")
    return cleaned or "noticia"


def _extrai_bloco(texto, nome):
    padrao = re.compile(
        r"\[" + nome + r"\]\s*(.*?)(?=\s*\[(?:INSTAGRAM|JORNALISTICO|ARTE)\]\s*|$)",
        re.DOTALL | re.IGNORECASE,
    )
    achado = padrao.search(texto)
    return achado.group(1).strip() if achado else ""


def _reduz_titulo(titulo, max_palavras=3):
    palavras = titulo.strip().split()
    return " ".join(palavras[:max_palavras])


def _reduz_subtitulo(texto, max_palavras=18):
    primeira_frase = re.split(r"[.\n]", texto.strip())[0]
    palavras = primeira_frase.split()
    return " ".join(palavras[:max_palavras])


def _limpa_credito(credito):
    """'Reprodução / Futebol Varginha TV' -> 'Futebol Varginha TV'."""
    credito = (credito or "").strip()
    if "/" in credito:
        credito = credito.split("/")[-1].strip()
    for prefixo in ("foto:", "credito:", "crédito:", "imagem:", "fotografia:"):
        if credito.lower().startswith(prefixo):
            credito = credito[len(prefixo):].strip()
    return credito or "Divulgação"


def extrai_credito_da_noticia(noticia):
    achado = re.search(r"(?im)^\s*(?:foto|cr[eé]dito|imagem|fotografia)\s*:\s*(.+)$", noticia)
    return _limpa_credito(achado.group(1)) if achado else ""


def chamar_ollama(noticia):
    import requests

    resposta = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": PROMPT_MODELO.format(noticia=noticia), "stream": False},
        timeout=(OLLAMA_CONNECT_TIMEOUT, OLLAMA_READ_TIMEOUT),
    )
    resposta.raise_for_status()
    corpo = resposta.json()
    if "response" not in corpo:
        raise RuntimeError(f"Resposta inesperada do Ollama: {corpo}")
    return corpo["response"]


def chamar_opencode(noticia):
    """Gera os blocos via `opencode run --format json` (sem usar ferramentas)."""
    import json as json_std

    prompt = (
        "Responda APENAS com o formato abaixo. NÃO use nenhuma ferramenta, "
        "não execute comandos, não leia nem crie arquivos.\n\n"
        + PROMPT_MODELO.format(noticia=noticia)
    )
    comando = [OPENCODE_BIN, "run", prompt, "--format", "json"]
    if OPENCODE_MODEL:
        comando += ["--model", OPENCODE_MODEL]
    with tempfile.TemporaryDirectory(prefix="gerador-noticias-") as vazio:
        try:
            proc = subprocess.run(
                comando,
                capture_output=True,
                timeout=OPENCODE_TIMEOUT,
                cwd=vazio,
            )
        except FileNotFoundError:
            raise RuntimeError(f"Executável '{OPENCODE_BIN}' não encontrado no PATH.")
        except subprocess.TimeoutExpired:
            raise RuntimeError("OpenCode demorou além do limite. Tente de novo.")
    saida = (proc.stdout or b"").decode("utf-8", errors="replace")
    erro = (proc.stderr or b"").decode("utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"OpenCode falhou: {(erro or saida)[-500:]}")
    textos = []
    for linha in saida.splitlines():
        linha = linha.strip()
        if not linha.startswith("{"):
            continue
        try:
            evento = json_std.loads(linha)
        except ValueError:
            continue
        if evento.get("type") == "text":
            parte = evento.get("part", {})
            if isinstance(parte, dict) and parte.get("text"):
                textos.append(parte["text"])
    resposta = "".join(textos).strip()
    if not resposta:
        raise RuntimeError("OpenCode não retornou texto.")
    return resposta


def gerar_bruto(noticia, provedor):
    if provedor == "ollama":
        return chamar_ollama(noticia)
    if provedor == "opencode":
        return chamar_opencode(noticia)
    raise ValueError(f"Provedor desconhecido: {provedor}. Use 'opencode' ou 'ollama'.")


def ensure_instagram_link_and_hashtags(texto):
    conteudo = texto.strip()
    linha_link = f"Saiba mais em: {SITE_URL}"
    conteudo = re.sub(
        r"(?:\U0001f310\s*)?Saiba mais em:\s*https?://terradorei\.com\.br/?",
        "",
        conteudo,
        flags=re.IGNORECASE,
    ).strip()
    achado = re.search(r"(?m)^\s*(?:HASHTAGS?:\s*)?(#\w+(?:\s+#\w+)*)\s*$", conteudo, flags=re.IGNORECASE)
    if achado:
        hashtags = achado.group(1).strip()
        corpo = (conteudo[:achado.start()] + conteudo[achado.end():]).strip()
    else:
        hashtags = DEFAULT_INSTAGRAM_HASHTAGS
        corpo = conteudo
    return f"{corpo}\n\n{linha_link}\n\n{hashtags}".strip()


def processar_noticia(noticia, credito_informado="", provedor=PROVEDOR_PADRAO):
    """Retorna dict com instagram, jornalistico, titulo_arte, subtitulo, credito."""
    bruto = gerar_bruto(noticia, provedor)

    instagram = _extrai_bloco(bruto, "INSTAGRAM") or "Texto Instagram não identificado"
    jornalistico = _extrai_bloco(bruto, "JORNALISTICO") or "Texto jornalístico não identificado"
    bloco_arte = _extrai_bloco(bruto, "ARTE")

    titulo_jornal = ""
    achado_titulo = re.search(r"(?im)^\s*T[íi]tulo\s*:\s*(.+)$", jornalistico)
    if achado_titulo:
        titulo_jornal = achado_titulo.group(1).strip()

    titulo_arte = ""
    subtitulo = ""
    credito_modelo = ""
    if bloco_arte:
        achado = re.search(r"(?im)^\s*TITULO\s*:\s*(.+)$", bloco_arte)
        if achado:
            titulo_arte = achado.group(1).strip()
        achado = re.search(r"(?im)^\s*SUBTITULO\s*:\s*(.+)$", bloco_arte)
        if achado:
            subtitulo = achado.group(1).strip()
        achado = re.search(r"(?im)^\s*CREDITO\s*:\s*(.*)$", bloco_arte)
        if achado:
            credito_modelo = achado.group(1).strip()

    if not titulo_arte:
        titulo_arte = _reduz_titulo(titulo_jornal or noticia.splitlines()[0], 3)
    else:
        titulo_arte = _reduz_titulo(titulo_arte, 3)

    if not subtitulo:
        corpo_jornal = re.sub(r"(?im)^\s*T[íi]tulo\s*:.*$", "", jornalistico).strip()
        subtitulo = _reduz_subtitulo(corpo_jornal or noticia, 18)
    else:
        subtitulo = " ".join(subtitulo.split()[:18])

    credito = _limpa_credito(
        credito_informado or credito_modelo or extrai_credito_da_noticia(noticia)
    )

    return {
        "instagram": ensure_instagram_link_and_hashtags(instagram),
        "jornalistico": jornalistico.strip(),
        "titulo_arte": titulo_arte,
        "subtitulo": subtitulo,
        "credito": credito,
    }


def nome_base_unico(diretorio, base):
    candidato = base
    contador = 2
    while (
        (diretorio / f"{candidato}_instagram.md").exists()
        or (diretorio / f"{candidato}_jornalistico.md").exists()
    ):
        candidato = f"{base}_{contador}"
        contador += 1
    return candidato
