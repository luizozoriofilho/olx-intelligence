import re
import json
import time
import base64
import logging
import random
from datetime import datetime
from curl_cffi import requests
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'database'))
from database import init_db, salvar_contato, buscar_ids_existentes, buscar_telefones_existentes
from notificador import enviar_telegram

# ============================================================
# CONFIGURAÇÃO DE LOGS
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"logs/scraper_{datetime.now().strftime('%Y%m%d')}.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================
URL_LISTAGEM = "https://www.olx.com.br/imoveis/venda/apartamentos/estado-rj/rio-de-janeiro-e-regiao/zona-oeste/recreio?ps=300000&pe=700000&f=p"
LIMITE_CONTATOS = 10
COOKIES_FILE = "cookies.json"
BANCO = "database/recreio.db"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

PALAVRAS_CORRETOR = [
    "creci", "imobiliária", "imobiliaria", "corretor", "corretora",
    "construtora", "incorporadora", "lançamento oficial", "stand de vendas",
    "plantão de vendas",
]

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def pausa_humana(minimo=1.0, maximo=3.5):
    segundos = random.uniform(minimo, maximo)
    time.sleep(segundos)

def carregar_cookies():
    try:
        with open(COOKIES_FILE) as f:
            cookies_list = json.load(f)
        cookies = {c["name"]: c["value"] for c in cookies_list}
        log.info(f"✅ {len(cookies_list)} cookies carregados.")
        return cookies
    except FileNotFoundError:
        log.error("❌ Arquivo cookies.json não encontrado. Execute salvar_cookies.py primeiro.")
        raise
    except Exception as e:
        log.error(f"❌ Erro ao carregar cookies: {e}")
        raise

def verificar_sessao(response):
    if "Faça login" in response.text or "login" in response.url:
        enviar_telegram("❌ OLX Scraper: Sessão expirada! Execute salvar_cookies.py")
        log.error("❌ Sessão expirada! Execute salvar_cookies.py para renovar os cookies.")
        raise Exception("Sessão expirada")
    if "Attention Required" in response.text or response.status_code == 403:
        enviar_telegram("❌ OLX Scraper: Bloqueado pelo Cloudflare!")
        log.error("❌ Bloqueado pelo Cloudflare!")
        raise Exception("Bloqueado pelo Cloudflare")

def extrair_next_data(html):
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL
    )
    if not match:
        return None
    return json.loads(match.group(1))

def eh_anuncio_corretor(html):
    """Retorna a palavra encontrada se for anúncio de corretor/imobiliária, senão None."""
    texto = re.sub(r'<[^>]+>', ' ', html).lower()
    for palavra in PALAVRAS_CORRETOR:
        if palavra in texto:
            return palavra
    return None

def extrair_telefone_descricao(html):
    texto_limpo = re.sub(r'<[^>]+>', ' ', html)
    padrao = re.search(r'\(?\b([1-9]{2})\)?[\s.-]?(9\d{4})[\s.-]?(\d{4})\b', texto_limpo)
    if padrao:
        return f"{padrao.group(1)}{padrao.group(2)}{padrao.group(3)}"
    return None

def buscar_telefone_api(list_id, cookies):
    try:
        r = requests.get(
            f"https://apigw.olx.com.br/v1/showphone/{list_id}",
            headers=HEADERS,
            cookies=cookies,
            impersonate="chrome120",
            timeout=15,
        )
        if r.status_code == 200:
            encoded = r.json().get("message", "")
            telefone = base64.b64decode(encoded).decode("utf-8")
            return telefone
        elif r.status_code == 429:
            log.warning("⚠️  Rate limit na API, pulando para descrição...")
            return None
        return None
    except Exception as e:
        log.warning(f"⚠️  Erro na API de telefone para {list_id}: {e}")
        return None

def buscar_html_anuncio(url_anuncio, cookies):
    """Busca o HTML da página do anúncio."""
    try:
        pausa_humana()
        r = requests.get(
            url_anuncio,
            headers=HEADERS,
            cookies=cookies,
            impersonate="chrome120",
            timeout=20,
        )
        return r.text
    except Exception as e:
        log.warning(f"⚠️  Erro ao acessar anúncio {url_anuncio}: {e}")
        return None

# ============================================================
# SCRAPER PRINCIPAL
# ============================================================

def executar():
    log.info("=" * 50)
    log.info("🚀 Iniciando scraper OLX")
    log.info("=" * 50)

    conn = init_db(BANCO)
    cookies = carregar_cookies()

    ids_existentes = buscar_ids_existentes(conn)
    telefones_vistos = buscar_telefones_existentes(conn)
    log.info(f"📂 {len(ids_existentes)} anúncios já salvos no banco.")

    coletados = 0
    pagina = 1

    while coletados < LIMITE_CONTATOS:
        url_pagina = f"{URL_LISTAGEM}&o={pagina}"
        log.info(f"\n📄 Buscando página {pagina}...")

        try:
            response = requests.get(
                url_pagina,
                headers=HEADERS,
                cookies=cookies,
                impersonate="chrome120",
                timeout=20,
            )
            verificar_sessao(response)
        except Exception as e:
            log.error(f"❌ Falha ao carregar página {pagina}: {e}")
            break

        data = extrair_next_data(response.text)
        if not data:
            log.warning("⚠️  __NEXT_DATA__ não encontrado. OLX pode ter mudado a estrutura.")
            break

        ads = data.get("props", {}).get("pageProps", {}).get("ads", [])
        if not ads:
            log.info("📭 Sem mais anúncios disponíveis.")
            break

        log.info(f"   {len(ads)} anúncios encontrados na página.")

        for ad in ads:
            if coletados >= LIMITE_CONTATOS:
                break

            titulo = ad.get("title") or ad.get("subject", "Sem título")
            preco = ad.get("price") or ad.get("priceValue", "Sem preço")
            url_anuncio = ad.get("url") or ad.get("friendlyUrl", "")
            list_id = str(ad.get("listId") or ad.get("list_id", ""))

            if list_id in ids_existentes:
                log.info(f"⏭️  Já salvo: {titulo[:40]}")
                continue

            log.info(f"📋 {titulo[:60]}")
            log.info(f"   💰 {preco}")

            telefone = None
            fonte = None
            html_anuncio = None

            # Tentativa 1: API oficial
            telefone = buscar_telefone_api(list_id, cookies)
            if telefone:
                fonte = "API"
                log.info(f"   📞 Telefone (API): {telefone}")

            # Tentativa 2: descrição do anúncio
            if not telefone and url_anuncio:
                html_anuncio = buscar_html_anuncio(url_anuncio, cookies)
                if html_anuncio:
                    # Verifica se é anúncio de corretor/imobiliária
                    motivo = eh_anuncio_corretor(html_anuncio)
                    if motivo:
                        log.info(f"   🏢 Anúncio de imobiliária ({motivo}), pulando...")
                        pausa_humana(0.5, 1.5)
                        continue

                    telefone = extrair_telefone_descricao(html_anuncio)
                    if telefone:
                        fonte = "descrição"
                        log.info(f"   📞 Telefone (descrição): {telefone}")

            if not telefone:
                log.info("   ⚠️  Sem telefone, pulando...")
                pausa_humana(0.5, 1.5)
                continue

            if telefone in telefones_vistos:
                log.info(f"   🔁 Telefone duplicado, pulando...")
                pausa_humana(0.5, 1.5)
                continue

            contato = {
                "titulo": titulo,
                "preco": preco,
                "telefone": telefone,
                "url": url_anuncio,
                "list_id": list_id,
                "fonte": fonte,
            }
            inserido = salvar_contato(conn, contato)
            if inserido:
                telefones_vistos.add(telefone)
                ids_existentes.add(list_id)
                coletados += 1
                log.info(f"   ✅ Salvo! ({coletados}/{LIMITE_CONTATOS})")

            pausa_humana()

        pagina += 1
        pausa_humana(2.0, 4.0)

    log.info("\n" + "=" * 50)
    log.info(f"🏁 Finalizado. {coletados} novos contatos coletados.")
    enviar_telegram(f"✅ OLX Scraper finalizado. {coletados} novos contatos coletados.")
    log.info("=" * 50)
    conn.close()

if __name__ == "__main__":
    import os
    os.makedirs("logs", exist_ok=True)
    executar()