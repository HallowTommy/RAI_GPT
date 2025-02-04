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

def get_token_info(contract_address):
    """ Получает данные о токене через Solscan API """
    url = f"https://pro-api.solscan.io/v2/token/meta?tokenAddress={contract_address}"
    headers = {"accept": "application/json", "token": SOLSCAN_API_KEY}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("data", {})
    else:
        logger.error("Ошибка Solscan API: %s", response.text)
        return None

@app.post("/chat")
async def chat_with_ai(body: RequestBody):
    """ Логика обработки двух сценариев: обычный чат и анализ токена """
    user_query = body.user_query.strip()
    logger.info("Получен запрос: %s", user_query)

    # Проверяем, есть ли в тексте Solana CA
    match = re.search(SOLANA_CA_PATTERN, user_query)
    
    if match:
        contract_address = match.group(0)
        logger.info("Обнаружен Solana CA: %s", contract_address)

        # Запрашиваем данные о токене
        token_data = get_token_info(contract_address)
        if not token_data:
            raise HTTPException(status_code=400, detail="Не удалось получить данные о токене.")

        # Подготавливаем запрос для OpenAI
        analysis_prompt = (
            f"Analyze the Solana token at {contract_address} with the following data: {token_data}"
        )

        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": analysis_prompt}
            ],
            "max_tokens": 300,
            "temperature": 0.7
        }

        try:
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            if response.status_code == 200:
                response_data = response.json()
                analysis = response_data["choices"][0]["message"]["content"]
                return {"contract_address": contract_address, "analysis": analysis}
            else:
                logger.error("Ошибка OpenAI API: %s", response.text)
                raise HTTPException(status_code=response.status_code, detail=response.text)
        except Exception as e:
            logger.error("Ошибка: %s", e)
            raise HTTPException(status_code=500, detail="Ошибка сервера.")
    else:
        # Если в запросе нет CA, просто отвечаем пользователю через OpenAI
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_query}
            ],
            "max_tokens": 300,
            "temperature": 0.8
        }

        try:
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            if response.status_code == 200:
                response_data = response.json()
                answer = response_data["choices"][0]["message"]["content"]
                return {"response": answer}
            else:
                logger.error("Ошибка OpenAI API: %s", response.text)
                raise HTTPException(status_code=response.status_code, detail=response.text)
        except Exception as e:
            logger.error("Ошибка: %s", e)
            raise HTTPException(status_code=500, detail="Ошибка сервера.")

@app.get("/")
async def root():
    return {"message": "RAI AI Chat & Token Analysis API. Use /chat to interact with AI or analyze tokens by CA."}
