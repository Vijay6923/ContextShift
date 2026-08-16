import json
import time
import requests
from tests.fixtures.legacy.config import Config

_MAX_RETRIES = 3
_BASE_BACKOFF = 5  # seconds

def call_groq(messages: list, max_tokens: int = 1024) -> str:
    """Shared helper to call the Groq API with automatic retry on rate limits."""
    if not Config.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set in environment.")

    headers = {
        "Authorization": f"Bearer {Config.GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": Config.GROQ_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7
    }

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = requests.post(
                Config.GROQ_BASE_URL,
                headers=headers,
                json=payload,
                timeout=30
            )

            # --- Rate limit: wait and retry ---
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", _BASE_BACKOFF * attempt))
                print(f"[GROQ] Rate limited (attempt {attempt}/{_MAX_RETRIES}). "
                      f"Waiting {retry_after}s before retry...")
                time.sleep(retry_after)
                continue  # retry

            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

        except requests.exceptions.RequestException as e:
            print(f"[GROQ API ERROR] attempt {attempt}: {str(e)}")
            if attempt == _MAX_RETRIES:
                # Friendly message for rate limit errors
                if "429" in str(e):
                    raise Exception(
                        "Groq rate limit reached. Please wait a moment and try again."
                    )
                raise Exception(f"Failed to call Groq API: {str(e)}")
            time.sleep(_BASE_BACKOFF * attempt)

    raise Exception("Groq API request failed after maximum retries.")

def call_groq_stream(messages: list, max_tokens: int = 1024):
    """Yields tokens from the Groq API in real-time."""
    if not Config.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set in environment.")

    headers = {
        "Authorization": f"Bearer {Config.GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": Config.GROQ_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "stream": True
    }

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = requests.post(
                Config.GROQ_BASE_URL,
                headers=headers,
                json=payload,
                timeout=30,
                stream=True
            )

            # Rate limit handling
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", _BASE_BACKOFF * attempt))
                time.sleep(retry_after)
                continue

            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue
                
                line_text = line.decode('utf-8')
                if line_text.startswith('data: '):
                    data_str = line_text[6:]
                    if data_str == '[DONE]':
                        break
                    
                    try:
                        data = json.loads(data_str)
                        delta = data['choices'][0]['delta']
                        if 'content' in delta:
                            yield delta['content']
                    except json.JSONDecodeError:
                        continue
            
            return # Success, exit retry loop

        except requests.exceptions.RequestException as e:
            if attempt == _MAX_RETRIES:
                raise Exception(f"Stream connection failed: {str(e)}")
            time.sleep(_BASE_BACKOFF * attempt)

def summarize_messages(messages: list) -> str:
    """Builds a conversation string and calls Groq to summarize it."""
    conversation_text = ""
    for msg in messages:
        role = "user" if msg.role == "user" else "assistant"
        conversation_text += f"{role}: {msg.content}\n"
    
    summary_prompt = [
        {
            "role": "system",
            "content": "You are a conversation summarizer. Summarize the following conversation excerpt into a single concise paragraph. Preserve all key facts, topics, and decisions. Be dense but accurate."
        },
        {
            "role": "user",
            "content": conversation_text
        }
    ]
    
    return call_groq(summary_prompt, max_tokens=512)
