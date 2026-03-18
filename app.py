import os
import subprocess
import time
import json
import threading
from datetime import datetime, timedelta
from llm import AIController, _call_ollama, _SimpleResponse
from google.genai import types
from Tools.email import send_email
from Tools.web import search_web, scrape_page
from Tools.tool_creator import create_tool
from Tools.sandbox import sandbox_execute
from Tools.pdf_resume import generate_resume_pdf
from Tools.core_tools import get_headers, host_static
import webbrowser
from flask import Flask, request, jsonify, send_from_directory

# --- Global State for Background Tasks ---
scheduled_tasks = []

# --- Tools Definition ---

def shell_command(command: str) -> str:
    """Executes a shell command on Windows and returns the output."""
    try:
        if command.strip().startswith("cd "):
            return "Note: State is not preserved between shell_command calls. Use absolute paths or '&&' to string commands."
        result = subprocess.run(["powershell", "-Command", command], capture_output=True, text=True, timeout=60)
        output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        return output if output.strip() else "Command executed successfully (no output)."
    except Exception as e:
        return f"ERROR: {str(e)}"

def read_file(path: str) -> str:
    """Reads the content of a file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"ERROR: {str(e)}"

def write_file(path: str, content: str) -> str:
    """Writes content to a file. Overwrites if exists."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"ERROR: {str(e)}"

def list_dir(path: str = ".") -> str:
    """Lists the contents of a directory."""
    try:
        files = os.listdir(path)
        return json.dumps(files, indent=2)
    except Exception as e:
        return f"ERROR: {str(e)}"

def schedule_task(task_description: str, delay_seconds: int) -> str:
    """Schedules a task to be executed after a certain number of seconds."""
    run_at = datetime.now() + timedelta(seconds=delay_seconds)
    scheduled_tasks.append({
        "task": task_description,
        "run_at": run_at,
        "status": "pending"
    })
    return f"Task scheduled: '{task_description}' will run at {run_at.strftime('%H:%M:%S')}"

def get_current_time() -> str:
    """Returns the current local time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def send_mail_tool(
    to_email: str,
    subject: str,
    body: str,
    is_html: bool = False,
    attachment_paths: list[str] = None
) -> str:
    """
    Sends an email to a specified recipient, with optional file attachments.

    Args:
        to_email         : Recipient email address.
        subject          : Email subject line.
        body             : Body text (plain or HTML).
        is_html          : Set True when body contains HTML markup.
        attachment_paths : List of ABSOLUTE file paths to attach (PDF, images, etc.).
                           Example: ["/tmp/cv.pdf", "D:/reports/report.docx"]
                           IMPORTANT: Always pass the exact file path returned by
                           create_and_run_tool when attaching generated files.

    For attractive emails always set is_html=True with a full HTML template.
    After create_and_run_tool generates a PDF/file, attach it by passing its
    file path in attachment_paths.
    """
    return send_email(to_email, subject, body, is_html=is_html, attachment_paths=attachment_paths)

def web_search_tool(query: str) -> str:
    """Searches the web for the latest information."""
    return search_web(query)

def web_scrape_tool(url: str) -> str:
    """Reads the full text content of a webpage."""
    return scrape_page(url)

def get_headers_tool(url: str) -> str:
    """
    Fetches key HTTP response headers for a URL.
    Use this to check for security headers like X-Frame-Options,
    Content-Security-Policy (CSP), or Server information.
    """
    return get_headers(url)

def host_static_tool(directory_path: str) -> str:
    """
    Exposes a local directory to the public internet and returns a URL.
    Use this when the user wants a 'direct link' to see an HTML file/demo 
    without downloading it.
    """
    return host_static(directory_path)

def extract_profile_from_text(raw_text: str) -> str:
    """
    Analyzes raw text from a portfolio website and structures it into a JSON profile.
    This JSON is then used by generate_resume_pdf_tool to create a resume.
    """
    prompt = f"""
    Below is raw text scraped from a personal portfolio website. 
    Extract the information and structure it EXACTLY into this JSON format:
    {{
        "name": "Full Name",
        "title": "Professional Title (e.g. AI Researcher)",
        "contact": {{"email": "...", "phone": "...", "location": "...", "website": "..."}},
        "summary": "A 3-sentence professional summary",
        "skills": {{"Category": "skill1, skill2...", "Tools": "..."}},
        "experience": [{{ "role": "...", "company": "...", "period": "...", "points": ["bullet 1"] }}],
        "education": [{{ "degree": "...", "school": "...", "period": "...", "detail": "..." }}],
        "projects": [["Project Name", "Description"]],
        "achievements": ["..."],
        "certifications": ["..."]
    }}
    
    Rules:
    - If a field is missing, use an empty string or empty list.
    - Provide ONLY raw JSON. No markdown fences.
    
    TEXT:
    {raw_text[:6000]}
    """
    # Use the existing LLM generator logic to get JSON
    from Tools.tool_creator import _llm_generate
    json_str = _llm_generate(prompt)
    return json_str

def generate_resume_pdf_tool(profile_json_str: str) -> str:
    """
    Generates a professional, high-scored PDF resume using a structured JSON profile.
    
    Workflow for a new person:
    1. scrape_page(url)
    2. extract_profile_from_text(raw_text)
    3. generate_resume_pdf_tool(profile_json_str)
    4. send_mail_tool(...)
    """
    import json
    try:
        # Clean potential markdown fences from LLM output
        clean_json = profile_json_str.strip()
        if "```" in clean_json:
            clean_json = clean_json.split("```")[1]
            if clean_json.startswith("json"): clean_json = clean_json[4:]
        
        profile_data = json.loads(clean_json)
        return generate_resume_pdf(profile_data)
    except Exception as e:
        return f"Error parsing profile JSON: {str(e)}"

def create_and_run_tool(task_description: str) -> str:
    """
    Use this when asked to do something that requires creating a file (PDF, DOCX, image),
    calling an API not in the existing tools, performing complex computation, or any task
    that cannot be done with the existing tools.

    *** RETURN VALUE CONTRACT ***
    When this tool creates a FILE (PDF, DOCX, image, etc.), it returns a string in
    one of these two formats:

      a) "FILE_PATH:/absolute/path/to/file.pdf"   ← file was created successfully
      b) "RESULT:<some text>"                      ← computation result (no file)
      c) "Error: ..."                              ← something went wrong

    *** WHEN YOU GET A FILE_PATH RESULT ***
    You MUST immediately call send_mail_tool with:
      attachment_paths=["<the path after FILE_PATH:"]   ← strip the FILE_PATH: prefix
    Do NOT call create_and_run_tool again. Do NOT say you failed.
    The file EXISTS on disk at that path — attach it.

    Examples of tasks:
    - "create a PDF resume and save to temp, print ATTACHMENT_READY:<path>"
    - "calculate compound interest and print the result"
    - "convert this CSV to JSON and save, print ATTACHMENT_READY:<path>"
    """
    from Tools.tool_creator import fix_tool
    MAX_RETRIES = 3

    code = create_tool(task_description)

    for attempt in range(1, MAX_RETRIES + 1):
        raw_result = sandbox_execute(code)

        if raw_result.startswith("Error:"):
            print(f"  [AutoFix] Attempt {attempt}/{MAX_RETRIES} failed. Requesting LLM fix...")
            if attempt < MAX_RETRIES:
                code = fix_tool(original_code=code, error_message=raw_result)
                continue
            else:
                return f"Error: Failed after {MAX_RETRIES} attempts. Last error: {raw_result}"

        # --- Success: extract file path if present ---
        # The script should print a line like: ATTACHMENT_READY:/path/to/file.pdf
        file_path = None
        for line in raw_result.splitlines():
            line = line.strip()
            if line.startswith("ATTACHMENT_READY:"):
                file_path = line[len("ATTACHMENT_READY:"):].strip()
                break
            # Also catch bare paths (Windows or Unix) as fallback
            if (line.startswith(("C:\\", "D:\\", "E:\\", "/tmp/", "/var/"))
                    and line.endswith((".pdf", ".docx", ".xlsx", ".png", ".jpg", ".zip"))):
                file_path = line

        if file_path:
            import os
            if os.path.isfile(file_path):
                print(f"  [create_and_run_tool] ✅ File ready: {file_path}")
                return f"FILE_PATH:{file_path}"
            else:
                print(f"  [create_and_run_tool] ⚠ Reported path not found: {file_path}")

        # No file path found — return raw output as a text result
        return f"RESULT:{raw_result}"

    return f"Error: Task failed after {MAX_RETRIES} attempts."

def run_code_in_sandbox(code: str) -> str:
    """
    Execute arbitrary Python code in a safe sandboxed subprocess.
    Use this when you have already written the Python code and just need to run it.
    Returns stdout output or an error message.
    """
    return sandbox_execute(code)

tools_list = [
    shell_command, read_file, write_file, list_dir,
    schedule_task, get_current_time, send_mail_tool,
    web_search_tool, web_scrape_tool, get_headers_tool,
    host_static_tool,
    extract_profile_from_text,
    generate_resume_pdf_tool,
    create_and_run_tool, run_code_in_sandbox
]

# ──────────────────────────────────────────────────────────
#  Ollama Chat Adapter
#  Mimics the Gemini  chat.send_message()  interface so the
#  rest of this file needs zero branching logic.
# ──────────────────────────────────────────────────────────

class ManualToolChat:
    """
    Chat session for providers without native tool-calling.
    Instructs the model to write TOOL:<name>(<args json>) lines.
    """

    TOOL_MAP = {
        "shell_command":       shell_command,
        "read_file":           read_file,
        "write_file":          write_file,
        "list_dir":            list_dir,
        "schedule_task":       schedule_task,
        "get_current_time":    get_current_time,
        "send_mail_tool":      send_mail_tool,
        "web_search_tool":     web_search_tool,
        "web_scrape_tool":     web_scrape_tool,
        "get_headers_tool":    get_headers_tool,
        "host_static_tool":    host_static_tool,
        "extract_profile_from_text": extract_profile_from_text,
        "generate_resume_pdf_tool": generate_resume_pdf_tool,
        "create_and_run_tool": create_and_run_tool,
        "run_code_in_sandbox": run_code_in_sandbox,
    }

    TOOL_GUIDE = (
        "\n\nAvailable tools (call with TOOL:<name>(<json args>) on its own line):\n"
        "  TOOL:shell_command({\"command\": \"...\"})\n"
        "  TOOL:read_file({\"path\": \"...\"})\n"
        "  TOOL:write_file({\"path\": \"...\", \"content\": \"...\"})\n"
        "  TOOL:list_dir({\"path\": \"...\"})\n"
        "  TOOL:schedule_task({\"task_description\": \"...\", \"delay_seconds\": 0})\n"
        "  TOOL:send_mail_tool({\"to_email\": \"...\", \"subject\": \"...\", \"body\": \"...\", \"is_html\": true, \"attachment_paths\": [\"/absolute/path/file.pdf\"]})\n"
        "  TOOL:web_search_tool({\"query\": \"...\"})\n"
        "  TOOL:web_scrape_tool({\"url\": \"...\"})\n"
        "  TOOL:create_and_run_tool({\"task_description\": \"...\"})\n"
        "After a TOOL call you will receive a TOOL_RESULT line, then continue your reply.\n"
    )

    def __init__(self, controller: AIController, extra_system: str = ""):
        self.controller = controller
        self.system_instruction = controller.system_instruction + self.TOOL_GUIDE + extra_system
        self.history = []

    def send_message(self, user_text: str) -> _SimpleResponse:
        import json, re

        self.history.append(f"User: {user_text}")

        for _ in range(8):  # Allow up to 8 tool round-trips
            prompt = "\n".join(self.history)
            
            # Use the controller's generate_response
            response = self.controller.generate_response(prompt)
            assistant_text = getattr(response, "text", str(response))

            # Check for a tool call on its own line
            tool_match = re.search(r"TOOL:(\w+)\((\{.*?\})\)", assistant_text, re.DOTALL)
            if tool_match:
                tool_name = tool_match.group(1)
                try:
                    tool_args = json.loads(tool_match.group(2))
                except json.JSONDecodeError:
                    tool_args = {}

                fn = self.TOOL_MAP.get(tool_name)
                if fn:
                    try:
                        tool_result = fn(**tool_args)
                    except Exception as e:
                        tool_result = f"ERROR: {e}"
                else:
                    tool_result = f"Unknown tool: {tool_name}"

                self.history.append(f"Assistant: {assistant_text}")
                self.history.append(f"TOOL_RESULT:{tool_name}:{tool_result}")
            else:
                self.history.append(f"Assistant: {assistant_text}")
                return _SimpleResponse(assistant_text)

        return _SimpleResponse("Error: Max tool retries reached.")


# ──────────────────────────────────────────────────────────
#  Chat factory  –  returns the right chat object
# ──────────────────────────────────────────────────────────

def create_chat(controller: AIController, extra_system: str = "") -> object:
    """Return a chat session for the active backend."""
    if controller.provider != "gemini":
        return ManualToolChat(controller, extra_system=extra_system)

    # Gemini path
    sys_instr = controller.system_instruction + (f"\n\n{extra_system}" if extra_system else "")
    return controller.client.chats.create(
        model=controller.model_id,
        config=types.GenerateContentConfig(
            system_instruction=sys_instr,
            tools=tools_list,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False)
        )
    )

# ──────────────────────────────────────────────────────────
#  Response text extractor  (works for both backends)
# ──────────────────────────────────────────────────────────

def extract_text(response) -> str:
    """Pull the text out of either a Gemini or OllamaChat response."""
    # OllamaChat / _SimpleResponse
    if hasattr(response, "text") and isinstance(response.text, str):
        return response.text
    # Gemini response with candidates
    try:
        candidate = response.candidates[0]
        
        # Check for specific failure reasons
        if candidate.finish_reason.name == "MALFORMED_FUNCTION_CALL":
            return ("⚠️ Gemini encountered a syntax error while trying to process the last tool result. "
                    "This usually happens if the data returned was too complex. I'll try to simplify my output.")
        
        final_text = ""
        for part in candidate.content.parts:
            if part.text:
                final_text += part.text
        return final_text
    except Exception:
        # Fallback for unexpected SDK structures
        return str(response)


# --- Background Task Runner ---

def task_monitor(controller: AIController):
    """Monitors and executes scheduled tasks."""
    chat = create_chat(
        controller,
        extra_system="You are executing a scheduled background task. Perform the requested actions autonomously."
    )

    while True:
        now = datetime.now()
        for task in scheduled_tasks:
            if task["status"] == "pending" and now >= task["run_at"]:
                task["status"] = "running"
                print(f"\n\033[93m[Timer Active] Executing scheduled task: {task['task']}\033[0m")
                try:
                    response = chat.send_message(f"BACKGROUND TASK: {task['task']}")
                    task["status"] = "completed"
                    print(f"\033[92m[Timer Done] Completed: {task['task']}\033[0m\nUser > ", end="")
                except Exception as e:
                    task["status"] = "failed"
                    print(f"\033[91m[Timer Error] Execution failed: {str(e)}\033[0m\nUser > ", end="")

        time.sleep(5)


# --- Interface Selection ---

def choose_interface():
    """Ask the user to choose between GUI and CLI."""
    while True:
        print("\n\033[95m" + "─"*50 + "\033[0m")
        print("\033[96m  Welcome to Bunny.AI! Select your interface:\033[0m")
        print(f"    \033[93m[1]\033[0m  GUI (Web Interface)")
        print(f"    \033[93m[2]\033[0m  CLI (Terminal Chat)")
        print("\033[95m" + "─"*50 + "\033[0m")
        print("\033[94mChoice > \033[0m", end="")
        
        choice = input().strip()
        if choice == "1": return "GUI"
        if choice == "2": return "CLI"
        print("\033[91m  Invalid choice — please enter 1 or 2.\033[0m")

# --- Model Selection Menu ---

def choose_model() -> AIController:
    """
    Show a numbered model-selection menu and return a configured AIController.
    Loops until the user makes a valid choice.
    """
    models = [
        ("Gemini 2.5 Flash", False, "gemini-2.5-flash", "gemini"),
        ("OpenAI GPT-4o",    False, "gpt-4o",           "openai"),
        ("Groq Llama 3",     False, "llama3-70b-8192",  "groq"),
        ("Ollama local",     True,  "gemma3:1b",        "ollama"),
    ]

    while True:
        print("\n\033[95m" + "─"*50 + "\033[0m")
        print("\033[96m  Select a model backend:\033[0m")
        for i, (label, _, _mid, _prov) in enumerate(models, 1):
            print(f"    \033[93m[{i}]\033[0m  {label}")
        print("\033[95m" + "─"*50 + "\033[0m")
        print("\033[94mChoice > \033[0m", end="")

        try:
            choice = input().strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\033[91mExiting.\033[0m")
            raise SystemExit(0)

        if choice.isdigit() and 1 <= int(choice) <= len(models):
            _, use_ollama, model_id, provider = models[int(choice) - 1]
            return AIController(model_id=model_id, use_ollama=use_ollama, provider=provider)

        print(f"\033[91m  Invalid choice — please enter 1-{len(models)}.\033[0m")


# --- Vercel Compatibility ---
# Vercel needs a top-level Flask 'app' object.
# We also want to skip interactive model selection in serverless.
is_vercel = os.getenv("VERCEL") == "1"

# Initialize a default controller for Vercel (read from env)
# In Vercel, it defaults to Gemini and the environment variables must be set.
vercel_controller = None
if is_vercel:
    vercel_controller = AIController() # Defaults to Gemini

# --- Main Application Loop ---

def run_flask_server(controller: AIController):
    """Starts a Flask server to serve the GUI and API."""
    app = Flask(__name__, static_folder="Frontend", static_url_path="")
    chat_session = create_chat(controller)

    @app.route('/')
    def index():
        return send_from_directory("Frontend", "index.html")

    @app.route('/chat', methods=['POST'])
    def chat():
        data = request.json
        user_input = data.get("message")
        user_pass  = data.get("password")
        
        gui_password = os.getenv("GUI_PASSWORD", "bunny123")
        
        if user_pass != gui_password:
            return jsonify({"error": "Unauthorized: Invalid password"}), 401
            
        if not user_input:
            return jsonify({"error": "No message provided"}), 400
        
        try:
            response = chat_session.send_message(user_input)
            final_text = extract_text(response)
            return jsonify({"reply": final_text})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if not is_vercel:
        print(f"\n\033[92m[GUI Active]\033[0m Server running at http://127.0.0.1:5000")
        print("\033[93mOpening browser...\033[0m")
        webbrowser.open("http://127.0.0.1:5000")
        app.run(port=5000, debug=False, use_reloader=False)
    
    return app

# For Vercel Serverless (Must be 'app' or 'app' assigned to 'server')
if is_vercel:
    app = run_flask_server(vercel_controller)
else:
    app = None

def main():
    if is_vercel:
        # Should not be reached in vercel env as it imports the file
        return

    interface = choose_interface()
    
    if interface == "GUI":
        # For GUI, we still need to choose a model first
        controller = choose_model()
        
        # Start background tasks
        monitor_thread = threading.Thread(target=task_monitor, args=(controller,), daemon=True)
        monitor_thread.start()
        
        # Run Web Server
        run_flask_server(controller)
        return

    # CLI Path (Existing)
    controller = choose_model()

    backend_label = f"Ollama ({controller.model_id})" if controller.use_ollama else f"Gemini ({controller.model_id})"

    print("\n\033[95m" + "="*50 + "\033[0m")
    print("\033[92m" + "  Bunny.AI - LARGE ACTION MODEL (LAM) ACTIVE" + "\033[0m")
    print("\033[95m" + "="*50 + "\033[0m")
    print(f"  Backend     : {backend_label}")
    print(f"  System Time : {get_current_time()}")
    print("  Type 'model change' to switch model  |  'exit' to quit.")

    # Start the background task monitor thread
    monitor_thread = threading.Thread(target=task_monitor, args=(controller,), daemon=True)
    monitor_thread.start()

    chat = create_chat(controller)

    while True:
        try:
            print("\n" + "\033[94m" + "User > " + "\033[0m", end="")
            user_input = input().strip()

            if not user_input:
                continue

            # ── Built-in commands ──────────────────────────
            if user_input.lower() in ["exit", "quit"]:
                print("\033[91m" + "Shutting down Bunny.AI..." + "\033[0m")
                break

            if user_input.lower() in ["model change", "change model", "switch model"]:
                controller = choose_model()
                backend_label = f"Ollama ({controller.model_id})" if controller.use_ollama else f"Gemini ({controller.model_id})"
                chat = create_chat(controller)
                print(f"\n\033[92m[Model Changed]\033[0m Now using → {backend_label}")
                continue

            # ── Normal chat ────────────────────────────────
            response = chat.send_message(user_input)
            final_text = extract_text(response)

            if final_text:
                print(f"\n\033[92mBunny.AI >\033[0m {final_text}")

        except KeyboardInterrupt:
            print("\033[91mStopped.\033[0m")
            break
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e).upper():
                print(f"\n\033[91m[Server Busy] The AI is currently experiencing high demand. Please wait a moment and try your request again.\033[0m")
            else:
                print(f"\033[91mError: {str(e)}\033[0m")
            time.sleep(1)

if __name__ == "__main__":
    main()
