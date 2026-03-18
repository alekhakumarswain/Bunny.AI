import os
import requests
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
#  Ollama helper  (gemma3:1b  – fully local)
# ──────────────────────────────────────────────

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL",    "gemma3:1b")

def _call_ollama(prompt: str, system_instruction: str = "") -> str:
    """Send a prompt to the local Ollama server and return the text reply."""
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")
    except requests.exceptions.ConnectionError:
        return (
            "[Ollama Error] Could not connect to Ollama. "
            "Make sure Ollama is running (`ollama serve`) and the model is pulled "
            f"(`ollama pull {OLLAMA_MODEL}`)."
        )
    except Exception as exc:
        return f"[Ollama Error] {exc}"

# ──────────────────────────────────────────────
#  OpenAI-Compatible Helper (OpenAI / Groq)
# ──────────────────────────────────────────────

def _call_openai_compatible(api_key: str, base_url: str, model: str, prompt: str, system_instruction: str = "") -> str:
    """Helper for OpenAI or Groq calls."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7
    }

    try:
        resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[Provider Error] {str(e)}"

# ──────────────────────────────────────────────
#  Simple response wrapper so callers can
#  always do  response.text  regardless of backend
# ──────────────────────────────────────────────

class _SimpleResponse:
    def __init__(self, text: str):
        self.text = text

# ──────────────────────────────────────────────
#  Main controller
# ──────────────────────────────────────────────

class AIController:
    """
    AIController supports multiple backends:

    1. Gemini  (default)  – cloud, full tool-calling support
    2. Ollama  (optional) – local gemma3:1b, no native tool-calling
    3. OpenAI  (optional) – cloud (gpt-4o)
    4. Groq    (optional) – lightning fast inference (llama3-70b)
    """

    def __init__(self, model_id: str = None, use_ollama: bool = False, provider: str = "gemini"):
        # Backwards compatibility for app.py
        if use_ollama:
            self.provider = "ollama"
        else:
            self.provider = provider.lower()
        
        self.model_id = model_id

        # Load system instruction
        role_path = os.path.join(os.path.dirname(__file__), "role.md")
        with open(role_path, "r", encoding="utf-8") as f:
            self.system_instruction = f.read()

        # Finalize use_ollama flag (used in app.py logic)
        self.use_ollama = (self.provider == "ollama")

        if self.provider == "ollama":
            self.model_id = self.model_id or OLLAMA_MODEL
            self.client   = None
            print(f"[LLM] Using local Ollama backend → {self.model_id}")
        
        elif self.provider == "openai":
            self.api_key = os.getenv("OPENAI_API_KEY")
            self.model_id = self.model_id or "gpt-4o"
            print(f"[LLM] Using OpenAI backend → {self.model_id}")
            
        elif self.provider == "groq":
            self.api_key = os.getenv("GROQ_API_KEY")
            self.model_id = self.model_id or "llama3-70b-8192"
            print(f"[LLM] Using Groq backend → {self.model_id}")

        else: # Gemini default
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            self.client   = genai.Client(api_key=api_key)
            self.model_id = self.model_id or "gemini-2.5-flash"
            print(f"[LLM] Using Gemini backend → {self.model_id}")

        self.history = []

    def generate_response(self, user_input: str, tools=None):
        """
        Generate a response from the active backend.
        Note: ONLY Gemini uses the native SDK tool flow.
        Other providers use 'Manual Tool Calling' in the chat adapter (app.py).
        """
        if self.provider == "ollama":
            text = _call_ollama(user_input, self.system_instruction)
            return _SimpleResponse(text)

        if self.provider == "openai":
            if not self.api_key: return _SimpleResponse("Error: OPENAI_API_KEY not found in .env")
            text = _call_openai_compatible(self.api_key, "https://api.openai.com/v1", self.model_id, user_input, self.system_instruction)
            return _SimpleResponse(text)

        if self.provider == "groq":
            if not self.api_key: return _SimpleResponse("Error: GROQ_API_KEY not found in .env")
            text = _call_openai_compatible(self.api_key, "https://api.groq.com/openai/v1", self.model_id, user_input, self.system_instruction)
            return _SimpleResponse(text)

        # Gemini path with Ollama fallback for robustness
        try:
            contents = [types.Content(role="user", parts=[types.Part.from_text(text=user_input)])]
            config   = types.GenerateContentConfig(
                system_instruction=self.system_instruction,
                tools=tools,
            )
            return self.client.models.generate_content(
                model=self.model_id,
                contents=contents,
                config=config,
            )
        except Exception as e:
            # Fallback to Ollama if cloud/API fails (e.g. RESOURCE_EXHAUSTED)
            err_msg = str(e).lower()
            if "exhausted" in err_msg or "unavailable" in err_msg or "503" in err_msg:
                print(f"  [LLM] Gemini issue detected: {err_msg[:50]}... Falling back to local Ollama.")
                text = _call_ollama(user_input, self.system_instruction)
                if not text.startswith("[Ollama Error]"):
                    return _SimpleResponse(f"[Fallback Active] {text}")
            
            # Re-raise if no fallback or different error
            raise e

if __name__ == "__main__":
    import sys
    # Quick test
    ai = AIController(provider="gemini")
    print("AI Controller initialized.")