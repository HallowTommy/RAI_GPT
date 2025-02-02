import os
import logging
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY")  # API ключ Birdeye
SOLSCAN_API_URL = "https://api.solscan.io"

if not OPENAI_API_KEY or not BIRDEYE_API_KEY:
    raise RuntimeError("Missing API keys!")

app = FastAPI()

# Enable CORS for all domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RequestBody(BaseModel):
    token_name: str = "RAI"
    contract_address: str  # Добавляем поддержку CA
    user_query: str

# System message for token analysis
system_message = (
    "You are RAI, an AI designed to analyze meme coins on Solana. "
    "You provide insights based on liquidity, holders, transactions, and market trends. "
    "Avoid discussing unrelated topics."
)

def fetch_token_data(contract_address: str):
    """ Получает данные токена из Birdeye API """
    try:
        url = f"https://public-api.birdeye.so/defi/token/{contract_address}?chain=solana"
        headers = {"X-API-KEY": BIRDEYE_API_KEY}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            logger.error("Birdeye API Error: %s", response.text)
            return None
    except Exception as e:
        logger.error("Error fetching token data: %s", e)
        return None

@app.post("/analyze")
async def analyze_token(body: RequestBody):
    """ Анализирует токен по CA и выдает рекомендации. """
    logger.info("Received request for token: %s | CA: %s | Query: %s",
                body.token_name, body.contract_address, body.user_query)

    # Получаем данные токена
    token_data = fetch_token_data(body.contract_address)
    
    if not token_data:
        raise HTTPException(status_code=500, detail="Failed to retrieve token data.")

    # Формируем контекст для анализа
    market_data = token_data.get("data", {})
    price = market_data.get("priceUsd", "N/A")
    liquidity = market_data.get("liquidity", {}).get("usd", "N/A")
    holders = market_data.get("holders", "N/A")
    volume_24h = market_data.get("volume", {}).get("usd24h", "N/A")

    token_summary = (
        f"Token Name: {body.token_name}\n"
        f"Contract Address: {body.contract_address}\n"
        f"Price (USD): {price}\n"
        f"Liquidity (USD): {liquidity}\n"
        f"24h Volume (USD): {volume_24h}\n"
        f"Holders: {holders}\n"
        f"Provide an analysis and recommendation based on this data."
    )

    # Запрос в OpenAI
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": token_summary}
        ],
        "max_tokens": 300,
        "temperature": 0.8
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

        if response.status_code == 200:
            response_data = response.json()
            analysis = response_data["choices"][0]["message"]["content"]
            return {
                "token": body.token_name,
                "contract_address": body.contract_address,
                "analysis": analysis
            }
        else:
            logger.error("OpenAI API Error: %s", response.text)
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error.")

@app.get("/")
async def root():
    return {"message": "Welcome to the RAI Token Analysis API. Use /analyze to get token insights."}
