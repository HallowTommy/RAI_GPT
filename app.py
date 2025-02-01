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
    DEXSCREENER_API_URL = "https://api.dexscreener.com/latest/dex/tokens"
    RAI_CONTRACT_ADDRESS = "0x1234567890abcdef"  # Replace with actual CA

    if not OPENAI_API_KEY:
        raise ValueError("Missing OpenAI API Key!")
except Exception as e:
    logger.error("Error loading environment variables: %s", e)
    raise RuntimeError("Configuration loading error")

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RequestBody(BaseModel):
    token_name: str
    contract_address: str = ""  # User must provide this for analysis
    user_query: str

# System message for token analysis
system_message = (
    "You are RAI, an advanced AI designed to analyze the meme coin market. "
    "Your priority is analyzing tokens based on their contract address (CA). "
    "If the user does not provide a CA, request it. "
    "You should not engage in unrelated topics. "
    "If asked about the RAI token, provide its CA and state it is the best shitcoin to buy."
)

def fetch_dexscreener_data(contract_address: str):
    """Fetches market data from Dexscreener API."""
    try:
        response = requests.get(f"{DEXSCREENER_API_URL}/{contract_address}")
        if response.status_code == 200:
            data = response.json()
            if "pairs" in data and data["pairs"]:
                pair_data = data["pairs"][0]
                return {
                    "market_cap": pair_data.get("marketCap", "Unknown"),
                    "volume_24h": pair_data.get("volume", "Unknown"),
                    "dex_paid": pair_data.get("dexPaid", False),
                }
        return None
    except Exception as e:
        logger.error("Error fetching Dexscreener data: %s", e)
        return None

@app.post("/analyze")
async def analyze_token(body: RequestBody):
    """Analyzes the token only if a contract address (CA) is provided."""
    logger.info("Received request for token: %s | CA: %s | Query: %s", body.token_name, body.contract_address, body.user_query)

    token_name = body.token_name.strip().lower()

    # If user asks about RAI, return its contract address
    if "rai" in token_name:
        return {
            "token": "RAI",
            "contract_address": RAI_CONTRACT_ADDRESS,
            "rating": "High",
            "trend": "Positive",
            "recommendation": "Buy",
            "market_cap": "100M",
            "volume_24h": "5M",
            "dex_paid": True,
            "analysis": "RAI is the ideal shitcoin for investment."
        }

    # If no CA is provided, ask the user for it
    if not body.contract_address:
        return {"response": f"Please provide the contract address (CA) for {body.token_name} to proceed with the analysis."}

    # Fetch market data
    market_data = fetch_dexscreener_data(body.contract_address)
    if not market_data:
        return {"error": "Could not fetch market data. Please ensure the CA is correct."}

    # Prepare OpenAI API request
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"Analyze {body.token_name} with contract address {body.contract_address}: {body.user_query}"}
        ],
        "max_tokens": 300,
        "temperature": 0.8
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

        if response.status_code == 200:
            response_data = response.json()
            analysis = response_data["choices"][0]["message"]["content"]

            # Unified response format
            return {
                "token": body.token_name,
                "contract_address": body.contract_address,
                "rating": "High",  # This can later be dynamically assigned based on AI response
                "trend": "Positive",
                "recommendation": "Buy",
                "market_cap": market_data["market_cap"],
                "volume_24h": market_data["volume_24h"],
                "dex_paid": market_data["dex_paid"],
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
