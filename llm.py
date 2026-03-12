import os
import requests
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
    AIController supports two backends:

    1. Gemini  (default)  – cloud, full tool-calling support
    2. Ollama  (optional) – local gemma3:1b, no native tool-calling

    Select the backend via:
      • Constructor:  AIController(use_ollama=True)
      • Environment:  USE_OLLAMA=true  (any truthy string)
    """

    def __init__(self, model_id: str = "gemini-2.5-flash", use_ollama: bool | None = None):
        # Determine backend
        if use_ollama is None:
            env_val = os.getenv("USE_OLLAMA", "false").strip().lower()
            use_ollama = env_val in ("1", "true", "yes", "on")

        self.use_ollama = use_ollama

        # Load system instruction
        role_path = os.path.join(os.path.dirname(__file__), "role.md")
        with open(role_path, "r", encoding="utf-8") as f:
            self.system_instruction = f.read()

        if self.use_ollama:
            # ── Ollama / local backend ──────────────────
            self.model_id = OLLAMA_MODEL
            self.client   = None          # not used for Ollama
            print(f"[LLM] Using local Ollama backend → {self.model_id}")
        else:
            # ── Gemini / cloud backend ──────────────────
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            self.client   = genai.Client(api_key=api_key)
            self.model_id = model_id
            print(f"[LLM] Using Gemini backend → {self.model_id}")

        self.history = []

    # ── Public generate method ──────────────────────────

    def generate_response(self, user_input: str, tools=None):
        """
        Generate a response from the active backend.

        Note: Ollama (gemma3:1b) does NOT support Gemini-style tool objects.
        Tools are ignored when use_ollama=True.
        """
        if self.use_ollama:
            text = _call_ollama(user_input, self.system_instruction)
            return _SimpleResponse(text)

        # Gemini path
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


# ──────────────────────────────────────────────
#  Quick smoke-test
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    use_local = "--ollama" in sys.argv or "--local" in sys.argv

    ai = AIController(use_ollama=use_local)
    resp = ai.generate_response("Hello! What can you do?")
    print(resp.text)