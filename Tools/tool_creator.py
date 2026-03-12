"""
tool_creator.py
---------------
Dynamically generates a Python script to solve tasks that Bunny.AI
cannot handle natively (e.g. creating PDFs, converting files, doing
precise calculations, accessing the local file system in complex ways).

Usage:
    from Tools.tool_creator import create_tool
    code = create_tool("create a PDF CV for Alekha Kumar Swain and save it to D:/cv.pdf")
    # Then execute with sandbox.sandbox_execute(code)
"""

import os
import re
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────
#  Low-level LLM call (Gemini only — no tool-calling needed here)
# ─────────────────────────────────────────────────────────────────

def _llm_generate(prompt: str) -> str:
    """Call Gemini (or Ollama fallback) and return plain text."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "You are an expert Python developer. "
                        "Output ONLY raw Python code with no markdown fences, "
                        "no triple backticks, and no explanations. "
                        "NEVER use CSS-style units like 0.2in — always use Python "
                        "numeric expressions like 0.2*inch from reportlab.lib.units."
                    )
                )
            )
            return response.text or ""
        except Exception as exc:
            print(f"  [ToolCreator] Gemini error: {exc}. Trying Ollama...")

    # Fallback: Ollama
    try:
        import requests
        ollama_url   = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ollama_model = os.getenv("OLLAMA_MODEL",    "gemma3:1b")
        resp = requests.post(
            f"{ollama_url}/api/chat",
            json={
                "model": ollama_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")
    except Exception as exc:
        return f"# ERROR generating tool: {exc}"


# ─────────────────────────────────────────────────────────────────
#  Code cleaner  (strips markdown fences)
# ─────────────────────────────────────────────────────────────────

def _clean_code(raw: str) -> str:
    """Strip markdown fences and leading noise from LLM output."""
    if not raw:
        return ""

    code = raw.strip()
    code = re.sub(r"^```[\w]*\s*", "", code, flags=re.MULTILINE)
    code = re.sub(r"\s*```$",      "", code, flags=re.MULTILINE)
    code = re.sub(r"```",          "", code)
    code = re.sub(r"^\s*python\s*\n", "", code, flags=re.IGNORECASE)
    code = code.strip()

    if not code:
        return "from datetime import date\nprint(date.today())"
    return code


# ─────────────────────────────────────────────────────────────────
#  Auto-patcher  (fixes known LLM mistakes before execution)
# ─────────────────────────────────────────────────────────────────

def _patch_code(code: str) -> str:
    """
    Automatically fix common LLM code generation mistakes so the
    sandbox doesn't fail on trivially bad output.

    Patches applied:
    1. CSS-style unit literals like 0.2in / 1in / .5in
       → 0.2*inch  (valid Python reportlab expression)
       Also injects `from reportlab.lib.units import inch` if missing.
    2. Any other patterns can be added here as they are discovered.
    """
    patched = code

    # ── Patch 1: CSS unit literals (e.g. 0.2in, 1in, .5in, 12.5in) ──
    # Must run BEFORE the inch import check
    inch_pattern = re.compile(r'(\b\d+\.?\d*|\.\d+)in\b')
    if inch_pattern.search(patched):
        # Replace  0.2in  →  0.2*inch
        patched = inch_pattern.sub(r'\1*inch', patched)

        # Inject the inch import if not already present
        if 'from reportlab.lib.units import' not in patched:
            # Insert right after the last reportlab import, or at the top
            rl_import = re.search(r'^(from reportlab\..+|import reportlab.+)$',
                                  patched, re.MULTILINE)
            if rl_import:
                insert_at = rl_import.end()
                patched = (patched[:insert_at]
                           + "\nfrom reportlab.lib.units import inch"
                           + patched[insert_at:])
            else:
                patched = "from reportlab.lib.units import inch\n" + patched
        elif 'inch' not in patched.split('from reportlab.lib.units import')[1].split('\n')[0]:
            # inch is not in the existing units import — add it
            patched = re.sub(
                r'(from reportlab\.lib\.units import\s+)(\w.*)',
                r'\1\2, inch',
                patched,
                count=1
            )
        print("  [ToolCreator] 🔧 Patched CSS unit literals (0.Xin → 0.X*inch)")

    return patched


# ─────────────────────────────────────────────────────────────────
#  Fix-from-error  (LLM self-correction given an error message)
# ─────────────────────────────────────────────────────────────────

def fix_tool(original_code: str, error_message: str) -> str:
    """
    Given code that failed to execute and the error message,
    ask the LLM to produce a fixed version.
    Returns clean, patched, executable Python source code.
    """
    prompt = f"""The following Python script failed to execute.

=== ERROR ===
{error_message}

=== ORIGINAL CODE ===
{original_code}

=== TASK ===
Fix ONLY the error(s) described above. Return the complete corrected Python script.

Critical rules:
- NEVER use CSS-style unit literals like 0.2in or 1in — use 0.2*inch from reportlab.lib.units import inch
- Do NOT use sys.argv or input()
- If the script creates a file, the very last print statement MUST be:
      print(f"ATTACHMENT_READY:{{output_path}}")
  where output_path is the full absolute path of the saved file.
- Output ONLY raw Python code — no markdown, no backticks, no explanations

Fixed Python code:"""

    print(f"  [ToolCreator] 🔁 Self-correcting from error: {error_message[:120]}")
    raw   = _llm_generate(prompt)
    code  = _clean_code(raw)
    code  = _patch_code(code)
    print(f"  [ToolCreator] ✅ Fixed code generated ({len(code)} chars).")
    return code


# ─────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────

def create_tool(task_description: str) -> str:
    """
    Ask the LLM to write a self-contained Python script that solves
    `task_description`. Returns clean, patched, executable Python code.
    """
    needs_pdf = any(kw in task_description.lower()
                    for kw in ["pdf", "cv", "resume", "report", "document"])

    pdf_rules = """
- For PDF generation use the `reportlab` library.
  Import: from reportlab.lib.pagesizes import A4, letter
          from reportlab.lib.units import inch, cm
          from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
          from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
          from reportlab.lib import colors
- CRITICAL: NEVER write CSS-style units like 0.2in or 1in directly in Python.
  Always write them as Python expressions: 0.2*inch, 0.5*cm, 1*inch etc.
- Save the PDF to a Windows temp path using:
      import tempfile, os
      output_path = os.path.join(tempfile.gettempdir(), 'output.pdf')
- The VERY LAST line of the script MUST be:
      print(f"ATTACHMENT_READY:{output_path}")""" if needs_pdf else ""

    file_output_rule = (
        "\n7. If the task creates a FILE, the very last print statement MUST be:\n"
        "       print(f\"ATTACHMENT_READY:{output_path}\")\n"
        "   where output_path is the full absolute path of the saved file.\n"
        "   This tag is required for the file to be emailed as an attachment."
        if needs_pdf else ""
    )

    prompt = f"""You have been asked to write a standalone Python script to solve the following task:

Task: {task_description}

Rules:
1. Use the Python standard library where possible.{pdf_rules}
2. The script MUST run immediately without any user interaction.
3. Do NOT use sys.argv or input(). Hardcode ALL values from the task directly into variables.
4. The script MUST print the FULL ABSOLUTE FILE PATH of any saved file as the very last action.
5. Handle all exceptions gracefully and print a clear error message if something fails.
6. Output ONLY raw Python code — no markdown, no backticks, no explanations.{file_output_rule}

Python code:"""

    print(f"  [ToolCreator] Generating code for: {task_description[:80]}...")
    raw  = _llm_generate(prompt)
    code = _clean_code(raw)
    code = _patch_code(code)   # ← auto-fix before first run
    print(f"  [ToolCreator] Code ready ({len(code)} chars).")
    return code
