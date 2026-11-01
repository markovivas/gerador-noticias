# Gerador de Notícias

Sistema autocontido para geração de notícias jornalísticas, publicações para Instagram e artes para capas.
Usa exclusivamente **OpenCode** para redação e **PhotoCraft** para edição e exportação das artes gráficas.

O modelo base oficial é `modelos\capa_noticia.psd` (mantido sempre intacto).

**Entrada:** informações/texto da notícia + uma imagem (JPG/PNG).  
**Saída:** arquivo Instagram (`.md`), arquivo jornalístico (`.md`), arquivo do projeto (`.psd`) e arte final (`.png`, 1080×1350).

---

## Como funciona

1. O usuário preenche o ID, data, texto da notícia, crédito da foto (opcional) e anexa a imagem em `GET /`.
2. `POST /gerar` executa de forma rápida e automatizada:
   - Salva uma cópia da foto enviada em `imagens\` (a foto original nunca é alterada);
   - Chama o **OpenCode** (`texto.py`) que devolve 3 blocos estruturados: `[INSTAGRAM]`, `[JORNALISTICO]` e `[ARTE]` (título ≤ 3 palavras, subtítulo ≤ 18 palavras, crédito);
   - Grava os arquivos `noticias\<slug>_instagram.md` e `noticias\<slug>_jornalistico.md`;
   - Executa o **PhotoCraft CLI** (`arte.py`) headlessly para editar o modelo PSD:
     - Camada `FOTO` (substituição do Smart Object pela foto enviada, preservando proporção, máscara e degradê);
     - Camada `TITULO` (edição do texto do título);
     - Camada `SUB-TITULO` (edição do texto do subtítulo);
     - Camada `CREDITO` (edição do texto do autor/divulgação da foto);
   - Salva o projeto em `projetos\noticia-ID-DD-MM-AAAA.psd`;
   - Converte e exporta `exports\noticia-ID-DD-MM-AAAA.png` (1080×1350);
3. A resposta JSON devolve os textos, nomes dos arquivos gerados e prévia imediata do PNG.

---

## Requisitos

- Python 3.10+, `pip install -r requirements.txt`
- **OpenCode**: CLI `opencode` instalado e no PATH do sistema.
- **PhotoCraft**: Instalado no caminho padrão (`C:\Program Files\ArtCraft\PhotoCraft\photocraft-cli.exe`) ou configurado pela variável de ambiente `PHOTOCRAFT_BIN`.

---

## Como executar

```bash
python app.py
```

Acesse `http://127.0.0.1:5000` no navegador. A geração completa leva apenas alguns segundos!

---

## Estrutura do projeto

```text
gerador-noticias/
|-- app.py                   # Servidor Flask (API e rotas)
|-- texto.py                 # Integração com OpenCode, prompt e regras jornalísticas
|-- arte.py                  # Orquestração do PhotoCraft CLI (edição de camadas e exportação PNG)
|-- modelos/
|   |-- capa_noticia.psd     # Modelo oficial em PSD (somente-leitura)
|-- imagens/                 # Fotos enviadas pelo usuário
|-- projetos/                # Projetos de trabalho (.psd) gerados
|-- exports/                 # Artes finais exportadas (.png 1080x1350)
|-- noticias/                # Arquivos de texto (.md) gerados
|-- templates/index.html     # Interface web do usuário
|-- static/style.css         # Folha de estilo da aplicação
|-- requirements.txt         # Dependências Python
```

---

## Regras de design preservadas

- O arquivo base `modelos\capa_noticia.psd` nunca é modificado diretamente.
- A camada `FOTO` utiliza Smart Object para manter a posição, máscara de recorte e o degradê superior (`Gradient Fill 1`).
- Os textos da arte respeitam as limitações de espaço da capa: título de até 3 palavras e subtítulo de até 18 palavras.
