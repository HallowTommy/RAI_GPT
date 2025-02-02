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

# System message for OpenAI
system_message = (
    "You are RAI, an advanced AI specializing in meme coin market analysis. "
    "If the user provides a contract address (CA), you must analyze the token and return a structured response: "
    "   token: [TOKEN NAME]\n"
    "   analysis: [SHORT ANALYSIS]\n"
    "   rating: [High/Medium/Low]\n"
    "   trend: [Positive/Neutral/Negative]\n"
    "   recommendation: [Buy/Hold/Sell]\n"
    "If no CA is provided, respond normally as an AI crypto assistant."
)

def fetch_token_data(contract_address):
    """Fetches token data from DEXScreener API"""
    response = requests.get(f"{DEXSCREENER_API_URL}{contract_address}")
    if response.status_code == 200:
        data = response.json()
        if "pairs" in data and len(data["pairs"]) > 0:
            return data["pairs"][0]
    return None

def analyze_token_with_openai(user_input):
    """Processes request through OpenAI API"""
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_input}
        ],
        "max_tokens": 300,
        "temperature": 0.8
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    if response.status_code == 200:
        response_data = response.json()
        return response_data["choices"][0]["message"]["content"]
    return "I'm currently unable to process this request."

@app.post("/analyze")
async def analyze_token(body: RequestBody):
    """Processes any user input, analyzing token if CA is present."""
    user_query = body.user_query.strip()
    logger.info("Received query: %s", user_query)

    # Extract contract address if available
    words = user_query.split()
    contract_address = next((word for word in words if len(word) > 25), None)

    if contract_address:
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
    
    # If no CA, process the request with OpenAI
    openai_response = analyze_token_with_openai(user_query)
    return {"message": openai_response}

@app.get("/")
async def root():
    return {"message": "Welcome to the RAI Token Analysis API. Use /analyze to get token insights."}
