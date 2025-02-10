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

# Регулярное выражение для поиска Solana CA
SOLANA_CA_PATTERN = r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b"

def get_token_info(ca):
    """ Получает информацию о токене """
    logger.info(f"🔍 Запрашиваем информацию о токене: {ca}")

    url = f"https://pro-api.solscan.io/v2.0/token/meta?address={ca}"
    headers = {"accept": "application/json", "Content-Type": "application/json", "token": SOLSCAN_API_KEY}

    try:
        response = requests.get(url, headers=headers)
        logger.info(f"🔄 Статус ответа (meta): {response.status_code}")
        
        if response.status_code == 200:
            data = response.json().get("data", {})
            if data:
                return {
                    "token_name": data.get("name", "Unknown"),
                    "total_supply": int(data.get("supply", 0)),
                }
        return {"error": "⚠️ Нет информации о токене."}
    except requests.RequestException as e:
        logger.error(f"❌ Ошибка при запросе к Solscan API: {e}")
        return {"error": "❌ Ошибка соединения с Solscan API."}

def get_token_first_transfers(ca, total_supply):
    """ Получает первые 20 реальных транзакций токена и считает % закупленного суплая """
    logger.info(f"🔍 Запрашиваем первые 20 транзакций (без минта) для токена: {ca}")

    url = (
        f"https://pro-api.solscan.io/v2.0/token/transfer?"
        f"address={ca}"
        f"&activity_type[]=ACTIVITY_SPL_TRANSFER"
        f"&page=1&page_size=20&sort_by=block_time&sort_order=asc"
    )

    headers = {"accept": "application/json", "Content-Type": "application/json", "token": SOLSCAN_API_KEY}

    try:
        response = requests.get(url, headers=headers)
        logger.info(f"🔄 Статус ответа Solscan: {response.status_code}")

        if response.status_code != 200:
            return {"error": "❌ Ошибка при запросе к Solscan API."}

        data = response.json().get("data", [])
        if not data:
            return {"error": "⚠️ Нет данных о первых транзакциях."}
        
        # Подсчет закупленного суплая
        total_bought = sum(tx.get("amount", 0) for tx in data)
        supply_percentage = round((total_bought / total_supply) * 100, 4) if total_supply else 0
        
        logger.info(f"✅ Закуплено {supply_percentage}% от общего суплая за первые 20 транзакций")
        return {"supply_bought_percent": supply_percentage}
    
    except requests.RequestException as e:
        logger.error(f"❌ Ошибка при запросе к Solscan API: {e}")
        return {"error": "❌ Ошибка соединения с Solscan API."}

@app.post("/analyze")
async def analyze_or_chat(body: RequestBody):
    """ Логика обработки двух сценариев: обычный чат и анализ токена """
    user_query = body.user_query.strip()
    logger.info("📩 Получен запрос: %s", user_query)

    match = re.search(SOLANA_CA_PATTERN, user_query)
    if match:
        ca = match.group(0)
        logger.info(f"📍 Найден контрактный адрес: {ca}")

        # Получаем информацию о токене
        token_info = get_token_info(ca)
        if "error" in token_info:
            return token_info

        # Запрашиваем процент купленного суплая
        supply_bought = get_token_first_transfers(ca, token_info["total_supply"])

        return {
            "contract_address": ca,
            "token_info": token_info,
            "supply_bought": supply_bought,
        }
    else:
        return {"response": "❌ Запрос не содержит корректный CA токена."}

@app.get("/")
async def root():
    return {"message": "RAI AI Chat & Token Analysis API. Use /analyze to interact with AI or analyze tokens by CA."}
