import os
import logging
import requests
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
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL")  # Например: "https://api.mainnet-beta.solana.com"

if not OPENAI_API_KEY or not SOLANA_RPC_URL:
    raise RuntimeError("Не хватает API ключей для OpenAI или Solana RPC!")

# Запуск FastAPI
app = FastAPI()

# Разрешаем CORS для всех доменов
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TokenRequest(BaseModel):
    contract_address: str

# Системное сообщение для OpenAI
system_message = (
    "You are RAI, an advanced AI designed to analyze the meme coin market. "
    "You provide insights into token trends, risks, and opportunities. "
    "You ONLY discuss topics related to shitcoins, meme coins, and the crypto market. "
    "You analyze a token whenever you detect a CA (Contract Address) in the Solana network. "
    "If a user provides a valid Solana contract address, you conduct an in-depth analysis, evaluating growth, popularity, and potential using real-time blockchain data."
)

def get_token_info(contract_address):
    """Получает данные о токене через Solana RPC."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAccountInfo",
        "params": [contract_address, {"encoding": "jsonParsed"}]
    }
    response = requests.post(SOLANA_RPC_URL, json=payload)

    if response.status_code == 200:
        data = response.json()
        return data.get("result", {}).get("value", {})
    else:
        logger.error("Ошибка Solana API: %s", response.text)
        return None

@app.post("/analyze")
async def analyze_token(body: TokenRequest):
    """Анализирует токен по контрактному адресу Solana"""
    ca = body.contract_address.strip()
    logger.info("Запрос анализа токена CA: %s", ca)

    # Получаем данные о токене
    token_data = get_token_info(ca)
    if not token_data:
        raise HTTPException(status_code=400, detail="Не удалось получить данные о токене.")

    # Формируем запрос в OpenAI
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"Analyze the Solana token at {ca} with the following data: {token_data}"}
        ],
        "max_tokens": 300,
        "temperature": 0.8
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        if response.status_code == 200:
            response_data = response.json()
            analysis = response_data["choices"][0]["message"]["content"]
            return {"contract_address": ca, "analysis": analysis}
        else:
            logger.error("Ошибка OpenAI API: %s", response.text)
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except Exception as e:
        logger.error("Ошибка: %s", e)
        raise HTTPException(status_code=500, detail="Ошибка сервера.")

@app.get("/")
async def root():
    return {"message": "RAI Token Analysis API. Отправьте контрактный адрес токена в сети Solana на /analyze."}
