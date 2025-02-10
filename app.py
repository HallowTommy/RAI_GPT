import os
import logging
import requests
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SOLSCAN_API_KEY = os.getenv("SOLSCAN_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("Не найден API-ключ OpenAI!")
if not SOLSCAN_API_KEY:
    raise RuntimeError("Не найден API-ключ Solscan!")

# FastAPI сервер
app = FastAPI()

# Разрешаем CORS для всех доменов
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RequestBody(BaseModel):
    user_query: str

# Регулярное выражение для поиска Solana CA (Public Key)
SOLANA_CA_PATTERN = r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b"

def get_token_info(ca):
    """ Получает информацию о токене """
    logger.info(f"🔍 Запрашиваем информацию о токене: {ca}")

    url = f"https://pro-api.solscan.io/v2.0/token/meta?address={ca}"
    headers = {"accept": "application/json", "token": SOLSCAN_API_KEY}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json().get("data", {})
            if data:
                return {
                    "token_name": data.get("name", "Unknown"),
                    "total_supply": int(data.get("supply", 0)),
                }
        return {"error": "⚠️ Нет информации о токене."}
    except requests.RequestException as e:
        logger.error(f"❌ Ошибка запроса к Solscan API: {e}")
        return {"error": "❌ Ошибка соединения с Solscan API."}


def get_token_first_transfers(ca):
    """ Получает первые 40 реальных транзакций токена (без минтинга) """
    logger.info(f"🔍 Запрашиваем первые 40 транзакций для токена: {ca}")

    url = (
        f"https://pro-api.solscan.io/v2.0/token/transfer?"
        f"address={ca}&activity_type[]=ACTIVITY_SPL_TRANSFER"
        f"&page=1&page_size=40&sort_by=block_time&sort_order=asc"
    )
    headers = {"accept": "application/json", "token": SOLSCAN_API_KEY}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get("data", [])
        return []
    except requests.RequestException as e:
        logger.error(f"❌ Ошибка запроса к Solscan API: {e}")
        return []


def analyze_transactions(transactions, total_supply):
    """ Анализирует транзакции на предмет инсайдерских переводов и фарма """
    if not transactions or total_supply == 0:
        return {"error": "⚠️ Недостаточно данных для анализа."}
    
    address_counts = {}
    total_purchased = 0

    for tx in transactions:
        sender = tx.get("from_address")
        receiver = tx.get("to_address")
        amount = int(tx.get("amount", 0))
        
        if receiver:
            address_counts[receiver] = address_counts.get(receiver, 0) + 1
        
        total_purchased += amount

    insider_addresses = [addr for addr, count in address_counts.items() if count > 1]
    farm_risk = (total_purchased / total_supply) * 100

    return {
        "insider_wallets": insider_addresses,
        "farm_risk_percent": round(farm_risk, 2),
    }

@app.post("/analyze")
async def analyze_or_chat(body: RequestBody):
    """ Логика обработки двух сценариев: обычный чат и анализ токена """
    user_query = body.user_query.strip()
    logger.info("📩 Получен запрос: %s", user_query)

    match = re.search(SOLANA_CA_PATTERN, user_query)

    if match:
        ca = match.group(0)
        logger.info(f"📍 Найден контрактный адрес: {ca}")

        token_info = get_token_info(ca)
        if "error" in token_info:
            return token_info

        transactions = get_token_first_transfers(ca)
        analysis = analyze_transactions(transactions, token_info["total_supply"])

        return {
            "contract_address": ca,
            "token_info": token_info,
            "transaction_analysis": analysis,
        }

    return {"response": "❌ Запрос не содержит корректный CA токена."}

@app.get("/")
async def root():
    return {"message": "RAI AI Chat & Token Analysis API."}
