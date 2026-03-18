# OLX Intelligence 🏠

Automação completa de prospecção imobiliária — do scraping ao envio de mensagens no WhatsApp.

## O que faz

Todo dia, automaticamente:
1. Scrapa anúncios de apartamentos na OLX
2. Filtra anúncios de imobiliárias e corretores (detecta CRECI, construtoras, etc.)
3. Extrai o telefone do proprietário via API interna da OLX ou descrição do anúncio
4. Envia mensagens personalizadas via WhatsApp Web
5. Notifica no Telegram quando termina ou quando os cookies expiram

## Destaques técnicos

- **Bypass do Cloudflare** via `curl_cffi` com impersonação de fingerprint TLS (Chrome 120)
- **Engenharia reversa** da API interna da OLX (`/v1/showphone/{listId}`) com decodificação Base64
- **Automação do WhatsApp Web** via Playwright conectado ao browser já aberto (CDP)
- **Teste A/B** de mensagens — 3 abordagens como cliente, 2 revelando que é corretor
- **Agendamento automático** via cron + Windows Task Scheduler
- **Banco SQLite** com deduplicação por telefone, list_id e URL

## Stack

- Python 3.12
- curl_cffi (Cloudflare bypass)
- Playwright (automação do WhatsApp Web)
- SQLite (banco de dados)
- Telegram Bot API (notificações)
- Cron + Windows Task Scheduler (agendamento)

## Estrutura

```
olx-intelligence/
├── database/
│   ├── database.py       # Operações SQLite
│   └── recreio.db        # Banco de dados (não versionado)
├── scraper/
│   ├── scraper.py        # Scraper principal
│   ├── whatsapp.py       # Envio de mensagens
│   ├── notificador.py    # Notificações Telegram
│   └── salvar_cookies.py # Renovação de cookies via Playwright
└── logs/                 # Logs diários (não versionados)
```

## Como funciona

### 1. Autenticação
O `salvar_cookies.py` abre um browser via Playwright, você faz login manualmente na OLX, e os cookies são salvos em `cookies.json`.

### 2. Scraping
O `scraper.py` usa `curl_cffi` para bypassar o Cloudflare e extrai os anúncios do JSON `__NEXT_DATA__` embutido na página. Para cada anúncio tenta buscar o telefone via API oficial — se não conseguir, acessa a página do anúncio e extrai via regex.

### 3. Envio de mensagens
O `whatsapp.py` conecta ao Edge/Chrome já aberto via CDP (porta 9222) e envia as mensagens automaticamente com digitação humanizada (delay aleatório entre teclas).

### 4. Agendamento
- **Windows Task Scheduler** abre o WSL e o Edge automaticamente às 15h58
- **Cron** dispara o `whatsapp.py` às 16h30
- **Task Scheduler** fecha tudo às 17h30

## Configuração

```bash
# Instalar dependências
pip install curl_cffi playwright requests

# Instalar browsers do Playwright
playwright install chromium

# Salvar cookies da OLX
python scraper/salvar_cookies.py
```

Configure o `notificador.py` com seu token e chat_id do Telegram.

## Aviso

Este projeto foi desenvolvido para uso pessoal. Respeite os termos de uso da OLX e do WhatsApp.
