# Gerador de Notícias

Sistema novo e autocontido — tudo vive nesta pasta. O modelo
`modelos\capa_noticia.af` é lido como base e nunca alterado.

**Entrada:** informações/texto + uma imagem (JPG/PNG).
**Saída:** arquivo Instagram (`.md`), arquivo jornalístico (`.md`) e PNG da arte.

## Como funciona

1. O usuário preenche ID, data, texto, crédito (opcional) e anexa a imagem em `GET /`.
2. `POST /gerar` executa, nesta ordem:
   - salva uma cópia nova da imagem em `imagens\` (originais nunca mudam);
   - chama o provedor de texto (`texto.py`) que devolve 3 blocos: `[INSTAGRAM]`, `[JORNALISTICO]` e `[ARTE]` (título ≤ 3 palavras, subtítulo ≤ 18, crédito);
   - grava `noticias\<slug>_instagram.md` e `noticias\<slug>_jornalistico.md`;
   - copia o modelo para `projetos\noticia-ID-DD-MM-AAAA.af` e edita **só** `TITULO`, `SUB-TITULO`, `DONO NA IMAGEM` e `FOTO` via MCP do Affinity (`arte.py` + `mcp_affinity.py`);
   - salva o `.af` e exporta `exports\noticia-ID-DD-MM-AAAA.png` (1080×1350, qualidade máxima).
3. A resposta traz os textos, os nomes dos arquivos e uma prévia do PNG.

## Requisitos

- Python 3.10+, `pip install -r requirements.txt`
- Um provedor de texto (escolhido no formulário):
  - **OpenCode** (padrão): CLI `opencode` no PATH, autenticado; usa `opencode run --format json`
    sem ferramentas, num diretório temporário vazio. Modelo padrão do OpenCode ou
    `GERADOR_MODEL=provedor/modelo`.
  - **Ollama**: rodando em `http://localhost:11434` com o modelo de `texto.py` (`gemma4:e2b`).
- Affinity aberto com o MCP habilitado (`http://[::1]:6767/sse`)

## Como executar

```bash
python app.py
```

Abrir `http://127.0.0.1:5000`. A geração do PNG pode levar 1–2 min.

## Estrutura

```text
gerador-noticias/
|-- app.py            # Flask: formulário + POST /gerar
|-- texto.py          # provedores (OpenCode/Ollama), parsing, regras de título/subtítulo/crédito
|-- arte.py           # copia o modelo, monta o JS e orquestra save/export
|-- mcp_affinity.py   # cliente MCP (stdlib, sem dependências extras)
|-- modelos/capa_noticia.af  # base somente-leitura
|-- docs/             # prompt-padrao.md + noticia-exemplo.txt (referência)
|-- imagens/          # fotos enviadas
|-- projetos/         # .af de trabalho
|-- exports/          # PNG finais
|-- templates/index.html
|-- static/style.css
|-- noticias/         # .md gerados
```

## Regras preservadas do padrão

- Modelo original intacto (tamanho/data verificados na cópia).
- Foto incorporada (não vinculada), cobertura proporcional sem deformar, máscara/gradiente/posição e ordem das camadas preservadas.
- Textos derivados só do conteúdo informado; crédito cai para "Divulgação" quando ausente.
