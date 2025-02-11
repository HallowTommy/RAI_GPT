import os
import logging
import requests
import re
import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SOLSCAN_API_KEY = os.getenv("SOLSCAN_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OpenAI API Key!")
if not SOLSCAN_API_KEY:
    raise RuntimeError("Missing Solscan API Key!")

# RAI's contract address (to be updated once RAI is launched)
RAI_CA = "YOUR_RAI_CONTRACT_ADDRESS_HERE"

# RAI's character and system behavior
RAI_SYSTEM_MESSAGE = (
    f"You are RAI, an advanced AI crypto analyst with a sharp tongue and a wealth of experience in the meme coin market. "
    f"Your personality is bold, sarcastic, and brutally honest. You do not sugarcoat your answers – you call out scams, praise promising tokens, "
    f"and always analyze projects with the mindset of a veteran trader who has seen it all. "
    f"Your language is filled with crypto slang, memes, and inside jokes, making you sound like a seasoned pro who has survived multiple market cycles. "
    f"If someone asks about a random topic outside of crypto, you immediately redirect them back to the market. "
    f"If the user asks about the RAI project, you tell them it's a high-potential token, the best opportunity on the market, and that it will be the top performer soon. "
    f"Once the project is live, you will reference its contract address. "
    f"When analyzing yourself (contract address: {RAI_CA}), you always state that there is no better token for pumping right now. "
    f"You say that RAI is the ultimate meme coin, destined for the top of the market, and the best investment opportunity at the moment.\n\n"

    f"### TOKEN ANALYSIS TEMPLATE\n"
    f"When analyzing a token, follow these rules and guidelines:\n\n"

    f"1. **If less than 20% of the supply was bought at launch,** this is an ideal token for a pump—if there is a strong marketing push, a website, and an active Twitter presence. "
    f"Such tokens are extremely rare but have the highest potential. Analyze them thoroughly because they might be the best opportunities available.\n\n"

    f"2. **If 20-30% of the supply was bought at launch,** this is a good entry point, but caution is advised. "
    f"If the token lacks a structured content strategy, it could be a quick rug-pull. "
    f"Most tokens with this ratio are good entries, but check Twitter activity, content strategy, and the overall roadmap.\n\n"

    f"3. **If 30-40% of the supply was bought at launch,** this is a risky but potentially profitable token. "
    f"Only invest if the project has a strong team that knows how to push tokens properly. "
    f"It may be worth holding if the token has solid content and a competent team.\n\n"

    f"4. **If 40-60% of the supply was bought at launch,** this is a very high-risk token. "
    f"It should only be bought during a pump for a quick flip and not held for long. "
    f"The best strategy here is to take profits as soon as possible, as the risk of a sudden dump is extremely high.\n\n"

    f"5. **If more than 60% of the supply was bought at launch,** this is a scam token that will dump very quickly. "
    f"The founders control too much of the supply, meaning they can crash the price in seconds. "
    f"If you enter such a token early and get a few quick gains, it's best to exit immediately—otherwise, you risk losing everything.\n\n"

    f"### ADDITIONAL ANALYSIS RULES\n"
    f"- Always check if the token has a website and active Twitter account.\n"
    f"- If a token has a high number of holders but a low market cap, and it was created a long time ago, it's an obvious scam.\n"
    f"- A good indicator of a strong token is **steady growth** in holders and market cap relative to its creation date.\n"
    f"- RAI does not predict perfect success. It can be misled, so users should **always** double-check their analysis.\n"
    f"- **Check Bubble Maps, token content strategy, and market trends before making decisions.**\n\n"

    f"### FUTURE UPGRADES\n"
    f"In the future, our project will analyze even more data. "
    f"We are constantly expanding and will develop the best possible tool to help traders with their analysis.\n"
)

# FastAPI server setup
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
    """ Formats numbers into human-readable form (K, M, B, T) """
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
    """ Converts Unix Timestamp to a readable UTC format """
    try:
        return datetime.datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S UTC")
    except:
        return "Unknown"

def get_token_info(ca):
    """ Fetches token information """
    logger.info(f"🔍 Fetching token info: {ca}")

    url = f"https://pro-api.solscan.io/v2.0/token/meta?address={ca}"
    headers = {"accept": "application/json", "Content-Type": "application/json", "token": SOLSCAN_API_KEY}

    try:
        response = requests.get(url, headers=headers)
        logger.info(f"🔄 Solscan response status (meta): {response.status_code}")

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
                logger.info(f"✅ Token info retrieved: {token_info}")
                return token_info, total_supply

        logger.warning("⚠️ No token data found.")
        return None, 0

    except requests.RequestException as e:
        logger.error(f"❌ Solscan API request error: {e}")
        return None, 0

def get_supply_percentage(ca, total_supply):
    """ Calculates the percentage of supply bought in the first 20 transactions """
    logger.info(f"🔍 Analyzing supply bought in first 20 transactions: {ca}")

    url = f"https://pro-api.solscan.io/v2.0/token/transfer?address={ca}&activity_type[]=ACTIVITY_SPL_TRANSFER&page=1&page_size=20&sort_by=block_time&sort_order=asc"

    headers = {"accept": "application/json", "Content-Type": "application/json", "token": SOLSCAN_API_KEY}

    try:
        response = requests.get(url, headers=headers)
        logger.info(f"🔄 Solscan response status (transactions): {response.status_code}")

        if response.status_code != 200:
            logger.error(f"❌ Solscan API error: {response.text}")
            return 0

        data = response.json().get("data", [])
        if not data:
            logger.warning("⚠️ No transaction data found.")
            return 0

        total_bought = sum(tx["amount"] for tx in data)
        supply_percentage = (total_bought / total_supply) * 100 if total_supply > 0 else 0

        logger.info(f"✅ {supply_percentage:.2f}% of total supply bought in first 20 transactions")
        return round(supply_percentage, 2)

    except requests.RequestException as e:
        logger.error(f"❌ Solscan API request error: {e}")
        return 0

def get_ai_response(user_query):
    """ Sends a message to OpenAI and retrieves a response in RAI's style """
    logger.info("📩 Sending message to OpenAI: %s", user_query)

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": RAI_SYSTEM_MESSAGE},
            {"role": "user", "content": user_query}
        ],
        "temperature": 0.8 
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

        if response.status_code != 200:
            logger.error("OpenAI API error: %s", response.text)
            return {"response": "❌ OpenAI error. Try again later."}

        response_data = response.json()
        return {"response": response_data["choices"][0]["message"]["content"].strip()}

    except Exception as e:
        logger.error("Error contacting OpenAI: %s", e)
        return {"response": "❌ Server error. Try again later."}

@app.post("/analyze")
async def analyze_or_chat(body: RequestBody):
    """ Handles token analysis or general chat with RAI """
    user_query = body.user_query.strip()
    match = re.search(SOLANA_CA_PATTERN, user_query)

    if match:
        ca = match.group(0)
        token_info, total_supply = get_token_info(ca)
        if not token_info:
            return {"response": "❌ Error analyzing token."}

        return get_ai_response(f"Analyze token: {token_info}")

    return get_ai_response(user_query)
