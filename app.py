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

def get_token_holders(ca):
    """ Получает список холдеров токена (максимум 40) """
    logger.info(f"🔍 Запрашиваем список холдеров для токена: {ca}")

    url = f"https://pro-api.solscan.io/v2.0/token/holders?address={ca}&page=1&page_size=40"

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "token": SOLSCAN_API_KEY
    }

    try:
        response = requests.get(url, headers=headers)
        logger.info(f"🔄 Статус ответа Solscan (holders): {response.status_code}")

        if response.status_code != 200:
            logger.error(f"❌ Ошибка Solscan API: {response.text}")
            return {"error": "❌ Ошибка при запросе к Solscan API."}

        data = response.json().get("data", [])

        # 🛠️ Добавляем лог структуры данных перед обработкой
        logger.info(f"🔍 Структура ответа (holders): {type(data)} - {data[:5] if isinstance(data, list) else data}")

        # Проверяем, является ли data списком
        if not isinstance(data, list) or not data:
            logger.warning("⚠️ Нет данных о холдерах токена или некорректный формат данных.")
            return {"error": "⚠️ Нет данных о холдерах токена."}

        holders = []
        for holder in data:
            if isinstance(holder, dict):  # Проверяем, является ли `holder` словарем
                holders.append({
                    "owner": holder.get("owner", "Unknown"),
                    "token_account": holder.get("token_account", "Unknown"),
                    "amount": holder.get("amount", "0"),
                    "value": holder.get("value", 0)
                })
            else:
                logger.warning(f"⚠️ Неожиданный формат холдера: {holder}")

        logger.info(f"✅ Получены {len(holders)} холдеров для токена {ca}")
        return holders

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

        # Получаем список холдеров токена
        holders = get_token_holders(ca)

        return {
            "contract_address": ca,
            "holders": holders
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
