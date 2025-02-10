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
        if response.status_code != 200:
            return {"error": "❌ Ошибка при запросе к Solscan API."}

        data = response.json().get("data", {})
        return {
            "token_name": data.get("name", "Unknown"),
            "token_symbol": data.get("symbol", "Unknown"),
            "icon_url": data.get("icon", ""),
            "total_supply": data.get("supply", "Unknown"),
            "holders_count": data.get("holder", 0),
            "creator": data.get("creator", "Unknown"),
            "market_cap": data.get("market_cap", "Unknown"),
            "description": data.get("metadata", {}).get("description", ""),
            "website": data.get("metadata", {}).get("website", ""),
            "twitter": data.get("metadata", {}).get("twitter", ""),
        }

    except requests.RequestException as e:
        return {"error": f"❌ Ошибка при запросе к Solscan API: {e}"}

def get_token_first_transfers(ca):
    """ Получает первые 10 реальных транзакций токена """
    logger.info(f"🔍 Запрашиваем первые 10 транзакций для токена: {ca}")
    url = f"https://pro-api.solscan.io/v2.0/token/transfer?address={ca}&activity_type[]=ACTIVITY_SPL_TRANSFER&page=1&page_size=10&sort_by=block_time&sort_order=asc"
    headers = {"accept": "application/json", "Content-Type": "application/json", "token": SOLSCAN_API_KEY}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return {"error": "❌ Ошибка при запросе к Solscan API."}

        data = response.json().get("data", [])
        return [
            {"tx_id": tx["trans_id"], "time": tx["time"], "from": tx["from_address"], "to": tx["to_address"], "amount": tx["amount"], "value": tx["value"]}
            for tx in data
        ]

    except requests.RequestException as e:
        return {"error": f"❌ Ошибка при запросе к Solscan API: {e}"}

def get_wallet_tokens(wallet_address, target_ca):
    """ Проверяет, есть ли у кошелька другие токены, кроме анализируемого """
    logger.info(f"🔍 Проверяем токены на кошельке: {wallet_address}")
    url = f"https://pro-api.solscan.io/v2.0/account/tokens?address={wallet_address}"
    headers = {"accept": "application/json", "Content-Type": "application/json", "token": SOLSCAN_API_KEY}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return {"error": "❌ Ошибка при запросе к Solscan API."}

        data = response.json().get("data", [])
        has_other_tokens = any(token["tokenAddress"] != target_ca for token in data)
        return {"only_target_token": not has_other_tokens}

    except requests.RequestException as e:
        return {"error": f"❌ Ошибка при запросе к Solscan API: {e}"}

def get_wallet_transactions(wallet_address, target_ca, first_holders):
    """ Проверяет, отправлял ли кошелек токены кому-то из первых 10 холдеров """
    logger.info(f"🔍 Анализируем переводы {wallet_address}")
    url = f"https://pro-api.solscan.io/v2.0/account/transactions?address={wallet_address}&limit=100"
    headers = {"accept": "application/json", "Content-Type": "application/json", "token": SOLSCAN_API_KEY}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return {"error": "❌ Ошибка при запросе к Solscan API."}

        data = response.json().get("data", [])
        insider_transfers = [tx for tx in data if tx["to"] in first_holders and tx["tokenAddress"] == target_ca]
        return {"insider_activity": len(insider_transfers) > 0, "transactions": insider_transfers}

    except requests.RequestException as e:
        return {"error": f"❌ Ошибка при запросе к Solscan API: {e}"}

@app.post("/analyze")
async def analyze_or_chat(body: RequestBody):
    """ Логика обработки двух сценариев: обычный чат и анализ токена """
    user_query = body.user_query.strip()
    match = re.search(SOLANA_CA_PATTERN, user_query)

    if match:
        ca = match.group(0)
        logger.info(f"📍 Найден контрактный адрес: {ca}")

        # Получаем информацию о токене
        token_info = get_token_info(ca)
        if "error" in token_info:
            return token_info

        # Получаем первые 10 транзакций
        first_transfers = get_token_first_transfers(ca)

        # Извлекаем адреса первых 10 получателей
        first_holders = [tx["to"] for tx in first_transfers if tx["to"]]

        # Проверяем, есть ли у первых холдеров другие токены
        holder_analysis = {wallet: get_wallet_tokens(wallet, ca) for wallet in first_holders}

        # Проверяем, есть ли инсайдерские переводы между первыми 10 холдерами
        insider_analysis = {wallet: get_wallet_transactions(wallet, ca, first_holders) for wallet in first_holders}

        return {
            "contract_address": ca,
            "token_info": token_info,
            "first_transfers": first_transfers,
            "holders_token_analysis": holder_analysis,
            "insider_transactions": insider_analysis
        }

    else:
        return {"response": "❌ Запрос не содержит корректный CA токена."}

@app.get("/")
async def root():
    return {"message": "RAI AI Chat & Token Analysis API. Use /analyze to interact with AI or analyze tokens by CA."}
