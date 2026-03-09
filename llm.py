import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class AIController:
    def __init__(self, model_id="gemini-2.5-flash"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            api_key = os.getenv("GOOGLE_API_KEY")
            
        self.client = genai.Client(api_key=api_key)
        self.model_id = model_id
        self.history = []
        
        # Load system instruction
        role_path = os.path.join(os.path.dirname(__file__), "role.md")
        with open(role_path, "r") as f:
            self.system_instruction = f.read()

    def generate_response(self, user_input, tools=None):
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=user_input)])]
        
        config = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            tools=tools
        )
        
        response = self.client.models.generate_content(
            model=self.model_id,
            contents=contents,
            config=config
        )
        
        return response

if __name__ == "__main__":
    ai = AIController()
    resp = ai.generate_response("Hello, what can you do?")
    print(resp.text)