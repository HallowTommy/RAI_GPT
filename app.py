import os
import logging
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    logger.error("Missing OpenAI API Key!")
    raise RuntimeError("OPENAI_API_KEY is required to run the server.")

app = FastAPI()

class RequestBody(BaseModel):
    token_name: str
    user_query: str

# System message для анализа токенов
system_message = (
    "You are RAI, the Shitcoin Market Analyzer. Your goal is to analyze meme coins, provide forecasts, and advise users on trading strategies."
    "Assess tokens based on their market trends, volume, community engagement, and potential for growth in the Solana ecosystem and beyond."
    "Users will provide a token name and ask for insights—offer detailed, data-driven responses."
)

@app.post("/analyze")
async def analyze_token(body: RequestBody):
    """
    Принимает название токена и запрос пользователя, отправляет их в OpenAI API, возвращает анализ.
    """
    logger.info("Received request for token: %s | Query: %s", body.token_name, body.user_query)

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"Analyze {body.token_name}: {body.user_query}"}
        ],
        "max_tokens": 300,
        "temperature": 0.8
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

        if response.status_code == 200:
            response_data = response.json()
            analysis = response_data["choices"][0]["message"]["content"]
            return {"token": body.token_name, "analysis": analysis}
        else:
            logger.error("OpenAI API Error: %s", response.text)
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error.")

@app.get("/")
async def root():
    return {"message": "Welcome to the RAI Token Analysis API. Use /analyze to get token insights."}
