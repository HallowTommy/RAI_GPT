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
    allow_origins=["*"],  # If you want to restrict, specify ['https://your-domain.com']
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Allow all headers
)

class RequestBody(BaseModel):
    user_query: str

# System message for token analysis
system_message = (
    "You are RAI, an advanced AI specializing in meme coin market analysis. "
    "Your goal is to analyze meme coins based on the given contract address (CA) and provide structured insights. "
    "Your response must follow this format: "
    "\n    token: [TOKEN NAME]"
    "\n    analysis: [SHORT ANALYSIS]"
    "\n    rating: [High/Medium/Low]"
    "\n    trend: [Positive/Neutral/Negative]"
    "\n    recommendation: [Buy/Hold/Sell]"
    "\n    If the user does not provide a contract address, kindly ask them to provide one."
)

@app.post("/analyze")
async def analyze_token(body: RequestBody):
    """Processes any user input, analyzing the token if a CA is present."""
    user_query = body.user_query.strip()
    logger.info("Received query: %s", user_query)

    # Extract contract address if available
    words = user_query.split()
    contract_address = next((word for word in words if len(word) > 25), None)

    if not contract_address:
        return {"message": "Please provide a valid contract address (CA) for analysis."}

    logger.info("Contract address detected: %s", contract_address)

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"Analyze token with CA: {contract_address}"}
        ],
        "max_tokens": 300,
        "temperature": 0.8
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

        if response.status_code == 200:
            response_data = response.json()
            analysis = response_data["choices"][0]["message"]["content"]
            logger.info("Returning AI-generated token analysis: %s", analysis)
            return {"token_analysis": analysis}
        else:
            logger.error("OpenAI API Error: %s", response.text)
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error.")

@app.get("/")
async def root():
    return {"message": "Welcome to the RAI Token Analysis API. Use /analyze with a valid contract address to get token insights."}
