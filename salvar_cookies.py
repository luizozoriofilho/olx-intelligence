import asyncio
import json
from playwright.async_api import async_playwright

async def salvar_cookies():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto("https://www.olx.com.br/login")
        
        print("Faça login manualmente no browser que abriu...")
        print("Depois que estiver logado, volte aqui e pressione ENTER")
        input()
        
        cookies = await context.cookies()
        with open("cookies.json", "w") as f:
            json.dump(cookies, f, indent=2)
        
        print(f"✅ {len(cookies)} cookies salvos em cookies.json")
        await browser.close()

asyncio.run(salvar_cookies())