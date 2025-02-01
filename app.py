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
try:
    load_dotenv()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        raise ValueError("Missing OpenAI API Key!")
except Exception as e:
    logger.error("Error loading environment variables: %s", e)
    raise RuntimeError("Configuration loading error")

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
    user_query: str

DEXSCREENER_API_URL = "https://api.dexscreener.com/latest/dex/tokens/"
RAI_CA = "0xYourRAITokenAddressHere"  # Replace with actual contract address

# System message for token analysis
system_message = (
    "You are RAI, an advanced AI specializing in meme coin market analysis. "
    "Your primary function is to analyze tokens when a user provides a contract address (CA). "
    "If the user does not provide a CA, you can respond to general crypto questions but avoid unrelated topics. "
    "Your responses should follow this structure:\n"
    "   token: [TOKEN NAME]\n"
    "   analysis: [SHORT ANALYSIS]\n"
    "   rating: [High/Medium/Low]\n"
    "   trend: [Positive/Neutral/Negative]\n"
    "   recommendation: [Buy/Hold/Sell]\n"
    "If a user asks about the RAI project, provide its CA and recommend it as an excellent token to buy."
)

def fetch_token_data(contract_address):
    """Fetches token data from DEXScreener API"""
    response = requests.get(f"{DEXSCREENER_API_URL}{contract_address}")
    if response.status_code == 200:
        data = response.json()
        if "pairs" in data and len(data["pairs"]) > 0:
            return data["pairs"][0]
    return None

@app.post("/analyze")
async def analyze_token(body: RequestBody):
    """Analyzes a token or responds to general crypto-related questions."""
    user_query = body.user_query.strip()
    logger.info("Received query: %s", user_query)

    # If the user asks about RAI, provide its CA and promote it
    if "rai" in user_query.lower():
        return {
            "token": "RAI",
            "contract_address": RAI_CA,
            "analysis": "RAI is a newly launched token with high potential.",
            "rating": "High",
            "trend": "Positive",
            "recommendation": "Buy"
        }

    # Extract contract address from user input
    words = user_query.split()
    contract_address = next((word for word in words if len(word) > 25), None)

    # If no CA found, check if it's a general crypto question
    if not contract_address:
        general_response = get_general_crypto_response(user_query)
        if general_response:
            return {"message": general_response}
        return {"message": "Please provide the contract address (CA) for analysis."}

    # Fetch token data from DEXScreener
    token_data = fetch_token_data(contract_address)
    if not token_data:
        return {"message": f"Could not retrieve data for CA: {contract_address}. Please check if it's correct."}

    # Extract relevant information
    token_name = token_data.get("baseToken", {}).get("name", "Unknown Token")
    market_cap = token_data.get("fdv", "N/A")
    trade_volume = token_data.get("volume", {}).get("h24", "N/A")
    trend = "Positive" if float(trade_volume) > 100000 else "Neutral" if float(trade_volume) > 10000 else "Negative"
    rating = "High" if float(market_cap) > 1000000 else "Medium" if float(market_cap) > 100000 else "Low"
    recommendation = "Buy" if rating == "High" and trend == "Positive" else "Hold" if rating == "Medium" else "Sell"

    return {
        "token": token_name,
        "contract_address": contract_address,
        "analysis": f"{token_name} is showing a {trend.lower()} trend with a market cap of ${market_cap} and 24h trading volume of ${trade_volume}.",
        "rating": rating,
        "trend": trend,
        "recommendation": recommendation
    }

def get_general_crypto_response(user_query):
    """Handles general crypto-related questions when no CA is provided."""
    if "market" in user_query.lower():
        return "The meme coin market is highly volatile. Always DYOR before investing."
    if "trend" in user_query.lower():
        return "Meme coin trends change rapidly. Look at social media sentiment and trading volume."
    if "investment" in user_query.lower():
        return "Investing in meme coins carries high risk. Diversify your portfolio wisely."
    if "best coin" in user_query.lower():
        return "There is no 'best' coin, but some popular meme coins include DOGE, SHIB, and BONK."
    return None

@app.get("/")
async def root():
    return {"message": "Welcome to the RAI Token Analysis API. Use /analyze to get token insights."}
