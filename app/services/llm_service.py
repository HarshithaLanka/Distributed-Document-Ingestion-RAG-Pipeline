# Import os so we can read Ollama settings from environment variables.
import os

# Import json so we can parse JSON responses from the LLM.
import json

# Import requests so Python can call the local Ollama API.
import requests

# Import HTTPException so FastAPI can return a clean error if Ollama fails.
from fastapi import HTTPException


# Read Ollama base URL from environment variable.
# If the variable is missing, use the default local Ollama URL.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Read Ollama model name from environment variable.
# If the variable is missing, use your current local model.
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b")


# This function sends a prompt to Ollama and returns the raw text response.
def generate_answer_from_ollama(prompt: str) -> str:
    # Build the full Ollama generate API URL.
    url = f"{OLLAMA_BASE_URL}/api/generate"

    # Create the request body that Ollama expects.
    payload = {
        # This tells Ollama which local model to use.
        "model": OLLAMA_MODEL,

        # This is the full RAG prompt containing context and question.
        "prompt": prompt,

        # This tells Ollama to return one full response instead of streaming tokens.
        "stream": False,

        # Options control how the model behaves.
        "options": {
            # Low temperature makes answers more stable and less creative.
            "temperature": 0.1,

            # This limits the answer length so small local models do not ramble.
            "num_predict": 700
        }
    }

    try:
        # Send the POST request to Ollama.
        response = requests.post(url, json=payload, timeout=120)

        # Raise an error if Ollama returns a bad HTTP status.
        response.raise_for_status()

    except requests.exceptions.RequestException as error:
        # Return a clean FastAPI error if Ollama is not running or failed.
        raise HTTPException(
            status_code=500,
            detail=f"Ollama request failed: {str(error)}"
        )

    # Convert Ollama's JSON response into a Python dictionary.
    data = response.json()

    # Return the generated response text from Ollama.
    return data.get("response", "").strip()


# This function safely tries to parse the LLM response as JSON.
def parse_llm_json_response(raw_response: str) -> dict:
    # Remove extra spaces around the raw response.
    cleaned_response = raw_response.strip()

    # Some models wrap JSON inside markdown code fences, so remove them.
    cleaned_response = cleaned_response.replace("```json", "").replace("```", "").strip()

    try:
        # Try to convert the cleaned response into a Python dictionary.
        return json.loads(cleaned_response)

    except json.JSONDecodeError:
        # If JSON parsing fails, return a safe fallback response.
        return {
            "answer": "I could not find this information in the document.",
            "used_chunk_ids": [],
            "answer_status": "not_found"
        }