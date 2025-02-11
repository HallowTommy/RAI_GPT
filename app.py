import os
import logging
import requests
import re
import datetime
from fastapi import FastAPI
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

def format_number(value):
    """ Форматирует числа в удобочитаемый вид (K, M, B, T) """
    if value >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:.2f}T"
    elif value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.2f}K"
    return str(value)

def format_timestamp(timestamp):
    """ Преобразует Unix Timestamp в удобный формат времени UTC """
    try:
        return datetime.datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S UTC")
    except:
        return "Unknown"

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
                total_supply = int(data.get("supply", 0))
                market_cap = float(data.get("market_cap", 0))

                token_info = {
                    "token_name": data.get("name", "Unknown"),
                    "token_symbol": data.get("symbol", "Unknown"),
                    "icon_url": data.get("icon", ""),
                    "total_supply": format_number(total_supply),
                    "holders_count": data.get("holder", 0),
                    "creator": data.get("creator", "Unknown"),
                    "created_time": format_timestamp(data.get("created_time", 0)),
                    "first_mint_tx": data.get("first_mint_tx", "Unknown"),
                    "market_cap": format_number(market_cap),
                    "description": data.get("metadata", {}).get("description", ""),
                    "website": data.get("metadata", {}).get("website", ""),
                    "twitter": data.get("metadata", {}).get("twitter", "")
                }
                logger.info(f"✅ Информация о токене получена: {token_info}")
                return token_info, total_supply

        logger.warning("⚠️ Нет информации о токене.")
        return None, 0

    except requests.RequestException as e:
        logger.error(f"❌ Ошибка при запросе к Solscan API: {e}")
        return None, 0

def get_supply_percentage(ca, total_supply):
    """ Считает процент суплая, купленного за первые 20 транзакций """
    logger.info(f"🔍 Анализируем процент закупленного суплая за первые 20 транзакций: {ca}")

    url = f"https://pro-api.solscan.io/v2.0/token/transfer?address={ca}&activity_type[]=ACTIVITY_SPL_TRANSFER&page=1&page_size=20&sort_by=block_time&sort_order=asc"

    headers = {"accept": "application/json", "Content-Type": "application/json", "token": SOLSCAN_API_KEY}

    try:
        response = requests.get(url, headers=headers)
        logger.info(f"🔄 Статус ответа Solscan: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"❌ Ошибка Solscan API: {response.text}")
            return 0

        data = response.json().get("data", [])
        if not data:
            logger.warning("⚠️ Нет данных о первых транзакциях.")
            return 0

        total_bought = sum(tx["amount"] for tx in data)
        supply_percentage = (total_bought / total_supply) * 100 if total_supply > 0 else 0

        logger.info(f"✅ Закуплено {supply_percentage:.2f}% от общего суплая в первых 20 транзакциях")
        return round(supply_percentage, 2)

    except requests.RequestException as e:
        logger.error(f"❌ Ошибка при запросе к Solscan API: {e}")
        return 0

@app.post("/analyze")
async def analyze_or_chat(body: RequestBody):
    """ Анализ токена или чат с RAI """
    user_query = body.user_query.strip()
    match = re.search(SOLANA_CA_PATTERN, user_query)

    if match:
        ca = match.group(0)
        token_info, total_supply = get_token_info(ca)
        if not token_info:
            return {"response": "❌ Ошибка при анализе токена. Проверьте правильность CA."}

        supply_percentage = get_supply_percentage(ca, total_supply)

        ai_comment = f"📢 **RAI говорит:** \"Ну, что я скажу… {supply_percentage}% токенов выкупили на старте – или это хомяки налетели, или инсайдеры набивают карманы. Холдеров пока немного, но если маркетинг пойдет – может взлететь. Держи руку на пульсе!\""

        return {
            "response": f"🔍 **Токен:** {token_info['token_name']} (${token_info['token_symbol']})\n"
                        f"📊 **Первые 20 транзакций закупили:** {supply_percentage}% от суплая\n\n{ai_comment}"
        }

    return {"response": "🚀 Дружище, чего хочешь? Мемкоины, инсайды, или просто рынок пообсуждать?"}
