import os
import subprocess
import time
import json
import threading
from datetime import datetime, timedelta
from llm import AIController
from google.genai import types
from Tools.email import send_email
from Tools.web import search_web, scrape_page

# --- Global State for Background Tasks ---
scheduled_tasks = []

# --- Tools Definition ---

def shell_command(command: str) -> str:
    """Executes a shell command on Windows and returns the output."""
    try:
        # Check if it's a 'cd' command - notify AI that it should use absolute paths
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

def send_mail_tool(to_email: str, subject: str, body: str) -> str:
    """Sends an email to a specified recipient."""
    return send_email(to_email, subject, body)

def web_search_tool(query: str) -> str:
    """Searches the web for the latest information."""
    return search_web(query)

def web_scrape_tool(url: str) -> str:
    """Reads the full text content of a webpage."""
    return scrape_page(url)

tools_list = [
    shell_command, read_file, write_file, list_dir, 
    schedule_task, get_current_time, send_mail_tool,
    web_search_tool, web_scrape_tool
]

# --- Background Task Runner ---

def task_monitor(controller):
    """Monitors and executes scheduled tasks."""
    chat = controller.client.chats.create(
        model=controller.model_id,
        config=types.GenerateContentConfig(
            system_instruction=controller.system_instruction + "\n\nYou are executing a scheduled background task. Perform the requested actions autonomously.",
            tools=tools_list,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False)
        )
    )
    
    while True:
        now = datetime.now()
        for task in scheduled_tasks:
            if task["status"] == "pending" and now >= task["run_at"]:
                task["status"] = "running"
                print(f"\n\033[93m[Timer Active] Executing scheduled task: {task['task']}\033[0m")
                try:
                    chat.send_message(f"BACKGROUND TASK: {task['task']}")
                    task["status"] = "completed"
                    print(f"\033[92m[Timer Done] Completed: {task['task']}\033[0m\nUser > ", end="")
                except Exception as e:
                    task["status"] = "failed"
                    print(f"\033[91m[Timer Error] Execution failed: {str(e)}\033[0m\nUser > ", end="")
        
        time.sleep(5)

# --- Main Application Loop ---

def main():
    controller = AIController() 
    
    print("\n\033[95m" + "="*50 + "\033[0m")
    print("\033[92m" + "  Bunny.AI - LARGE ACTION MODEL (LAM) ACTIVE" + "\033[0m")
    print("\033[95m" + "="*50 + "\033[0m")
    print(f"  System Time: {get_current_time()}")
    print("  Ready to perform tasks. Type 'exit' to stop.")
    
    # Start the background task monitor thread
    monitor_thread = threading.Thread(target=task_monitor, args=(controller,), daemon=True)
    monitor_thread.start()

    chat = controller.client.chats.create(
        model=controller.model_id,
        config=types.GenerateContentConfig(
            system_instruction=controller.system_instruction,
            tools=tools_list,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False)
        )
    )

    while True:
        try:
            print("\n" + "\033[94m" + "User > " + "\033[0m", end="")
            user_input = input().strip()
            
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("\033[91m" + "Shutting down Bunny.AI..." + "\033[0m")
                break
                
            response = chat.send_message(user_input)
            
            final_text = ""
            for part in response.candidates[0].content.parts:
                if part.text:
                    final_text += part.text
            
            if final_text:
                print(f"\n\033[92mBunny.AI >\033[0m {final_text}")

        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e).upper():
                print(f"\n\033[91m[Server Busy] The AI is currently experiencing high demand. Please wait a moment and try your request again.\033[0m")
            else:
                print(f"\033[91mError: {str(e)}\033[0m")
            time.sleep(1)

if __name__ == "__main__":
    main()
