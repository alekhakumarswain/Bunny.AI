
from Tools.core_tools import get_headers, host_static
import time
import os

print("--- Testing get_headers ---")
try:
    headers = get_headers("https://alekhakumarswain.web.app")
    print(headers)
except Exception as e:
    print(f"Failed: {e}")

print("\n--- Testing host_static ---")
os.makedirs("test_demo", exist_ok=True)
with open("test_demo/index.html", "w") as f:
    f.write("<h1>Test Clickjacking Demo</h1>")

print("Starting host...")
start_time = time.time()
url = host_static("test_demo")
end_time = time.time()
print(f"Result: {url}")
print(f"Time taken: {end_time - start_time:.2f}s")
