import asyncio
import random
import logging
import sys, os
from datetime import datetime
from playwright.async_api import async_playwright

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'database'))
from database import init_db, buscar_pendentes, marcar_enviado
from notificador import enviar_telegram

log = logging.getLogger(__name__)

# ============================================================
# MENSAGENS - TESTE A/B
# ============================================================
# Grupo A (sem revelar corretor) - índices 0, 1, 2
# Grupo B (revelando corretor)   - índices 3, 4

MENSAGENS = [
    # Grupo A
    "{saudacao}! Vi seu anúncio de apartamento e fiquei interessado. Você ainda está vendendo?",
    "{saudacao}! Encontrei seu anúncio e tenho interesse no imóvel. Você é o proprietário?",
    "{saudacao}! Seu apartamento me chamou atenção. Ainda está disponível?",
    # Grupo B
    "{saudacao}! Me chamo Luiz Eduardo, sou corretor da IMOBI. Estou assessorando clientes que buscam imóveis no {bairro} e encontrei seu anúncio. Você é o proprietário?",
    "{saudacao}! Sou o Luiz Eduardo, corretor da IMOBI. Tenho clientes procurando imóveis na sua região e seu anúncio chamou atenção. Você é o dono do imóvel?",
]

def saudacao_atual():
    hora = datetime.now().hour
    if hora < 12:
        return "Bom dia"
    elif hora < 18:
        return "Boa tarde"
    else:
        return "Boa noite"

def extrair_bairro(url):
    partes = url.lower().split("/")
    bairros_conhecidos = ["recreio", "barra", "jacarepagua", "campo-grande", "tijuca", "ipanema", "copacabana", "botafogo"]
    for parte in partes:
        for bairro in bairros_conhecidos:
            if bairro in parte:
                return bairro.replace("-", " ").title()
    return "sua região"

def montar_mensagem(url, indice_dia):
    template = MENSAGENS[indice_dia % len(MENSAGENS)]
    return template.format(
        saudacao=saudacao_atual(),
        bairro=extrair_bairro(url or "")
    )

async def enviar_whatsapp(telefone, mensagem):
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://IP_DO_PC:PORT")
        context = browser.contexts[0]
        page = context.pages[0]

        url = f"https://web.whatsapp.com/send?phone=55{telefone}&text="
        await page.goto(url)

        await page.wait_for_selector('div[contenteditable="true"][data-tab="10"]', timeout=30000)
        await asyncio.sleep(2)

        campo = page.locator('div[contenteditable="true"][data-tab="10"]')
        await campo.click()
        await campo.type(mensagem, delay=random.randint(30, 80))
        await asyncio.sleep(1)

        await page.keyboard.press("Enter")
        await asyncio.sleep(2)

        log.info(f"   📤 Mensagem enviada para {telefone}")
        await browser.close()

async def executar():
    log.info("=" * 50)
    log.info("📱 Iniciando envio de mensagens WhatsApp")
    log.info("=" * 50)

    conn = init_db()
    contatos = buscar_pendentes(conn, limite=8)

    if not contatos:
        log.info("📭 Nenhum contato pendente para enviar.")
        enviar_telegram("📭 WhatsApp: Nenhum contato pendente. Rode o scraper para coletar mais.")
        conn.close()
        return

    indice_dia = datetime.now().timetuple().tm_yday

    enviados = 0
    for contato in contatos:
        id_, titulo, preco, telefone, url, list_id, fonte, enviada, data_envio, criado_em, descartado, motivo_descarte, tipo_mensagem = contato

        log.info(f"📋 {titulo[:50]}")
        log.info(f"   📞 {telefone}")

        mensagem = montar_mensagem(url or "", indice_dia + enviados)
        grupo = "A" if (indice_dia + enviados) % len(MENSAGENS) < 3 else "B"
        tipo_mensagem = "cliente" if grupo == "A" else "corretor"
        log.info(f"   📝 Grupo {grupo}: {mensagem[:60]}...")

        try:
            await enviar_whatsapp(telefone, mensagem)
            marcar_enviado(conn, id_, tipo_mensagem)
            enviados += 1
            log.info(f"   ✅ Enviado! ({enviados}/8)")
        except Exception as e:
            log.error(f"   ❌ Erro ao enviar para {telefone}: {e}")

        await asyncio.sleep(random.uniform(60, 180))

    log.info("\n" + "=" * 50)
    log.info(f"🏁 Finalizado. {enviados} mensagens enviadas.")
    log.info("=" * 50)

    enviar_telegram(f"📱 WhatsApp: {enviados} mensagens enviadas com sucesso!")
    conn.close()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(f"logs/whatsapp_{datetime.now().strftime('%Y%m%d')}.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    asyncio.run(executar())