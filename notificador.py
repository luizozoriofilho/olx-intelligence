import requests

TOKEN = "SEU_TOKEN_AQUI"
CHAT_ID = "SEU_CHAT_ID_AQUI"

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/botCODIGO_BOT:API_TELEGRAM/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": mensagem})