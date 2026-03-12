"""
sandbox.py
----------
Executes arbitrary Python code in an isolated subprocess (sandbox).
Captures stdout/stderr, enforces a timeout, and cleans up temp files.

Usage:
    from Tools.sandbox import sandbox_execute
    result = sandbox_execute(python_code_string)
    print(result)   # stdout output or error message
"""

import os
import re
import sys
import subprocess
import tempfile


# ─────────────────────────────────────────────────────────────────
#  Code sanitiser
# ─────────────────────────────────────────────────────────────────

def _clean_sandbox_code(code: str) -> str:
    """Strip any residual markdown fences from code before execution."""
    if not code:
        return ""

    # Remove markdown fences
    code = re.sub(r"^```[\w]*\s*", "", code, flags=re.MULTILINE)
    code = re.sub(r"\s*```$",      "", code, flags=re.MULTILINE)
    code = re.sub(r"```",          "", code)

    # If there's no print statement, wrap the last expression
    if "print(" not in code:
        lines = code.strip().splitlines()
        last = lines[-1].strip() if lines else ""
        if (
            last
            and not last.startswith(("import ", "from ", "def ", "class ", "#"))
            and "=" not in last
        ):
            lines[-1] = f"print({last})"
            code = "\n".join(lines)

    return code.strip()


# ─────────────────────────────────────────────────────────────────
#  Sandbox executor
# ─────────────────────────────────────────────────────────────────

def sandbox_execute(code: str, timeout: int = 300) -> str:
    """
    Run `code` in a sandboxed subprocess using the same Python interpreter.

    Args:
        code    : Python source code to execute.
        timeout : Maximum execution time in seconds (default 300 = 5 min).

    Returns:
        stdout output on success, or a descriptive error string.
    """
    code = _clean_sandbox_code(code)
    if not code:
        return "Error: No code to execute."

    # Store temp scripts in a dedicated sandbox_env directory
    sandbox_dir = os.path.join(os.path.dirname(__file__), "sandbox_env")
    os.makedirs(sandbox_dir, exist_ok=True)

    temp_file = None
    try:
        # Write to a named temp file so tracebacks show a meaningful path
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            dir=sandbox_dir,
            delete=False,
            encoding="utf-8"
        ) as f:
            f.write(code)
            temp_file = f.name

        print(f"  [Sandbox] Executing: {os.path.basename(temp_file)} ...")

        result = subprocess.run(
            [sys.executable, temp_file],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=sandbox_dir          # isolate working directory
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            print(f"  [Sandbox] ✅ Execution successful.")
            return output if output else "Execution completed successfully (no output)."
        else:
            # Prefer stderr; fall back to stdout
            err = (result.stderr or result.stdout or "").strip()

            # Extract just the last meaningful error line (skip traceback noise)
            if "Traceback" in err:
                for line in reversed(err.splitlines()):
                    line = line.strip()
                    if line and not line.startswith("File ") and not line.startswith("  "):
                        err = line
                        break

            print(f"  [Sandbox] ❌ Execution failed: {err}")
            return f"Error: {err}"

    except subprocess.TimeoutExpired:
        msg = f"Error: Sandbox timeout — code took longer than {timeout}s."
        print(f"  [Sandbox] ⏱ {msg}")
        return msg

    except Exception as exc:
        msg = f"Error: Sandbox error — {exc}"
        print(f"  [Sandbox] ⚠ {msg}")
        return msg

    finally:
        # Always clean up the temp file
        if temp_file:
            try:
                os.unlink(temp_file)
            except OSError:
                pass


# ─────────────────────────────────────────────────────────────────
#  Quick self-test
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_code = """
import math
result = math.factorial(10)
print(f"10! = {result}")
"""
    print("Self-test result:", sandbox_execute(test_code))
