import os
import logging
import requests
import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
SOLSCAN_API_KEY = os.getenv("SOLSCAN_API_KEY")

if not SOLSCAN_API_KEY:
    raise RuntimeError("Не найден API-ключ Solscan!")

# FastAPI сервер
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RequestBody(BaseModel):
    user_query: str

SOLANA_CA_PATTERN = r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b"

def get_token_first_transfers(ca):
    url = (
        f"https://pro-api.solscan.io/v2.0/token/transfer?"
        f"address={ca}&activity_type[]=ACTIVITY_SPL_TRANSFER"
        f"&page=1&page_size=10&sort_by=block_time&sort_order=asc"
    )
    headers = {"accept": "application/json", "Content-Type": "application/json", "token": SOLSCAN_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return []
        data = response.json().get("data", [])
        return [
            {"tx_id": tx["trans_id"], "to": tx["to_address"], "amount": tx["amount"]}
            for tx in data
        ]
    except requests.RequestException:
        return []

def get_token_info(ca):
    url = f"https://pro-api.solscan.io/v2.0/token/meta?address={ca}"
    headers = {"accept": "application/json", "Content-Type": "application/json", "token": SOLSCAN_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return {}
        data = response.json().get("data", {})
        return {
            "total_supply": data.get("supply", "Unknown"),
        }
    except requests.RequestException:
        return {}

def analyze_initial_holders(ca):
    first_transfers = get_token_first_transfers(ca)
    if not first_transfers:
        return {"error": "Нет данных о первых транзакциях."}

    token_info = get_token_info(ca)
    total_supply = int(token_info.get("total_supply", "0"))
    if total_supply == 0:
        return {"error": "Некорректный supply токена."}

    buyers = {}
    for tx in first_transfers:
        to_address = tx["to"]
        amount = int(tx["amount"])
        if to_address not in buyers:
            buyers[to_address] = 0
        buyers[to_address] += amount

    analyzed_holders = []
    for holder, amount in buyers.items():
        percentage = (amount / total_supply) * 100
        airdrop_check = check_airdrop(holder, ca)
        analyzed_holders.append({
            "holder": holder,
            "amount": amount,
            "percentage_of_supply": round(percentage, 4),
            "possible_airdrop": airdrop_check
        })
    return analyzed_holders

def check_airdrop(wallet, ca):
    url = (
        f"https://pro-api.solscan.io/v2.0/account/transactions?"
        f"address={wallet}&limit=10"
    )
    headers = {"accept": "application/json", "Content-Type": "application/json", "token": SOLSCAN_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return "Ошибка при запросе"
        data = response.json().get("data", [])
        for tx in data:
            if tx.get("to", "") != wallet and tx.get("token_address", "") == ca:
                return "Да"
        return "Нет"
    except requests.RequestException:
        return "Ошибка при анализе"

@app.post("/analyze")
async def analyze_or_chat(body: RequestBody):
    user_query = body.user_query.strip()
    match = re.search(SOLANA_CA_PATTERN, user_query)
    if match:
        ca = match.group(0)
        analysis_result = analyze_initial_holders(ca)
        return {"contract_address": ca, "initial_holders_analysis": analysis_result}
    return {"response": "❌ Запрос не содержит корректный CA токена."}
