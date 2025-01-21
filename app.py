from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import openai
import json
import re
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("shrokai_server.log"),  # Лог в файл
        logging.StreamHandler()  # Лог в консоль
    ]
)
logger = logging.getLogger("ShrokAI")

# Initialize FastAPI
app = FastAPI()

# OpenAI API Configuration
openai.api_key = "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"
openai.organization = "org-yB4Zen11yEPm7qjKN5tvW9EX"

# Character description for prompt
character_description = """
Your name is ShrokAI, a green ogre streamer obsessed with psychoactive mushrooms.
They grant you visions of the crypto market’s future and summon the black dwarf.
You are a swamp prophet of memecoins, a mushroom-fueled shaman, and a die-hard Solana enthusiast.
Try to always answer briefly.
"""

# Function to clean text before sending to TTS
def clean_text_for_tts(text):
    logger.info("Cleaning response text for TTS")
    allowed_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,!?()'\"-:; "
    cleaned_text = "".join(c for c in text if c in allowed_chars)
    cleaned_text = re.sub(r'([.,!?;:-])\1+', r'\1', cleaned_text)
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text.replace("\n", " ").replace("\r", " "))
    logger.debug(f"Cleaned text: {cleaned_text}")
    return cleaned_text.strip()

# Function to generate ShrokAI's response using OpenAI API
def generate_shrokai_response(user_input, history):
    logger.info(f"Generating response for user input: {user_input}")
    prompt = f"{character_description}\n\n{'\n'.join(history[-20:])}\nUser: {user_input}\nShrokAI:"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "system", "content": character_description},
                      {"role": "user", "content": user_input}],
            max_tokens=150,
            temperature=0.7,
            top_p=0.9
        )
        response_text = response['choices'][0]['message']['content'].strip()
        logger.info(f"Generated response: {response_text}")
        return response_text
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return "Sorry, something went wrong with my mushroom visions!"

# WebSocket endpoint for AI processing
@app.websocket("/ws/ai")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    history = []
    logger.info("WebSocket connection established")
    try:
        while True:
            message = await websocket.receive_text()
            logger.info(f"Received message from client: {message}")

            # Generate response
            response = generate_shrokai_response(message, history)
            cleaned_response = clean_text_for_tts(response)

            # Update conversation history
            history.append(f"User: {message}")
            history.append(f"ShrokAI: {response}")

            # Send response back to client
            response_data = json.dumps({"response": cleaned_response})
            await websocket.send_text(response_data)
            logger.info(f"Sent response to client: {cleaned_response}")

    except WebSocketDisconnect:
        logger.warning("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await websocket.close(code=1001)

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting ShrokAI server")
    uvicorn.run(app, host="0.0.0.0", port=7979)
