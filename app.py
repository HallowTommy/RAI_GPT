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

# Системное сообщение для OpenAI
system_message = (
    "You are RAI, an advanced AI designed to analyze the meme coin market. "
    "You provide users with insights into token trends, risks, and opportunities. "
    "You ONLY discuss topics related to shitcoins, meme coins, and the crypto market. "
    "If a user asks about something unrelated to crypto, politely redirect them back to the topic."
)

# Регулярное выражение для поиска Solana CA (Public Key)
SOLANA_CA_PATTERN = r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b"

def get_token_info(ca):
    """ Получает полную информацию о токене, включая метаданные """
    logger.info(f"🔍 Запрашиваем информацию о токене: {ca}")

    url = f"https://pro-api.solscan.io/v2.0/token/meta?address={ca}"

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "token": SOLSCAN_API_KEY
    }

    try:
        response = requests.get(url, headers=headers)
        logger.info(f"🔄 Статус ответа (meta): {response.status_code}")

        if response.status_code != 200:
            logger.error(f"❌ Ошибка Solscan API: {response.text}")
            return {"error": "❌ Ошибка при запросе к Solscan API."}

        data = response.json().get("data", {})
        if not data:
            logger.warning("⚠️ Нет информации о токене.")
            return {"error": "⚠️ Нет информации о токене."}

        # Формируем объект с полной информацией
        token_info = {
            "contract_address": data.get("address", ca),
            "token_name": data.get("name", "Unknown"),
            "token_symbol": data.get("symbol", "Unknown"),
            "icon_url": data.get("icon", ""),
            "decimals": data.get("decimals", 0),
            "total_supply": data.get("supply", "Unknown"),
            "holders_count": data.get("holder", 0),
            "creator": data.get("creator", "Unknown"),
            "created_time": data.get("created_time", "Unknown"),
            "first_mint_tx": data.get("first_mint_tx", "Unknown"),
            "market_cap": data.get("market_cap", "Unknown"),
            "price": data.get("price", "Unknown"),
        }

        # Если есть доп. метаданные, подтягиваем их
        metadata = data.get("metadata", {})
        token_info["description"] = metadata.get("description", "No description available")
        token_info["website"] = metadata.get("website", "No website available")
        token_info["twitter"] = metadata.get("twitter", "No Twitter available")

        logger.info(f"✅ Успешно получена информация о токене: {token_info}")
        return token_info

    except requests.RequestException as e:
        logger.error(f"❌ Ошибка при запросе к Solscan API: {e}")
        return {"error": "❌ Ошибка соединения с Solscan API."}


def get_token_first_transfers(ca):
    """ Получает первые 10 реальных транзакций токена (без минтинга) """
    logger.info(f"🔍 Запрашиваем первые транзакции (без минта) для токена: {ca}")

    url = (
        f"https://pro-api.solscan.io/v2.0/token/transfer?"
        f"address={ca}"
        f"&activity_type[]=ACTIVITY_SPL_TRANSFER"
        f"&page=1&page_size=10&sort_by=block_time&sort_order=asc"
    )

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "token": SOLSCAN_API_KEY
    }

    try:
        response = requests.get(url, headers=headers)
        logger.info(f"🔄 Статус ответа Solscan: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"❌ Ошибка Solscan API: {response.text}")
            return {"error": "❌ Ошибка при запросе к Solscan API."}

        data = response.json().get("data", [])
        if not data:
            logger.warning("⚠️ Нет данных о первых транзакциях.")
            return {"error": "⚠️ Нет данных о первых транзакциях токена."}

        first_transfers = []
        for tx in data:
            first_transfers.append({
                "tx_id": tx["trans_id"],
                "time": tx["time"],
                "from": tx["from_address"],
                "to": tx["to_address"],
                "amount": tx["amount"],
                "value": tx["value"]
            })

        logger.info(f"✅ Получены первые {len(first_transfers)} транзакции для токена {ca}")
        return first_transfers

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

        # Запрашиваем первые 10 реальных транзакций токена (без минта)
        first_transfers = get_token_first_transfers(ca)

        return {
            "contract_address": ca,
            "token_info": token_info,
            "first_transfers": first_transfers
        }

    else:
        # Обычный чат с ИИ
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_query}
            ],
            "max_tokens": 150,
            "temperature": 0.8
        }

        try:
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

            if response.status_code != 200:
                logger.error("Ошибка OpenAI API: %s", response.text)
                return {"error": "❌ Ошибка OpenAI. Попробуйте позже."}

            response_data = response.json()
            answer = response_data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

            if not answer:
                logger.error("OpenAI API вернул пустой ответ")
                return {"error": "❌ OpenAI API не дал ответа. Попробуйте другой запрос."}

            logger.info("Ответ от OpenAI: %s", answer)
            return {"response": answer}

        except Exception as e:
            logger.error("Ошибка при запросе к OpenAI: %s", e)
            return {"error": "❌ Ошибка сервера. Попробуйте позже."}

@app.get("/")
async def root():
    return {"message": "RAI AI Chat & Token Analysis API. Use /analyze to interact with AI or analyze tokens by CA."}
