
import os
import subprocess
import time
import json
import socket
import sys
import requests

def get_headers(url: str) -> str:
    """
    Fetches key HTTP response headers for a URL.
    """
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        response = requests.head(url, timeout=10, allow_redirects=True)
        h = response.headers
        
        important = ["X-Frame-Options", "Content-Security-Policy", "Strict-Transport-Security", "Server", "X-Content-Type-Options"]
        results = []
        for key in important:
            if key in h:
                results.append(f"{key}: {h[key]}")
        
        if not results:
            return "No security headers found (potentially vulnerable)."
        
        return "\n".join(results)
    except Exception as e:
        return f"Error fetching headers: {str(e)}"

def host_static(directory_path: str) -> str:
    """
    Exposes a local directory to the public internet and returns a URL.
    """
    directory_path = os.path.abspath(directory_path)
    if not os.path.isdir(directory_path):
        return f"Error: {directory_path} is not a directory."

    # Find an open port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()

    # Start Python HTTP server in that directory (background)
    subprocess.Popen([sys.executable, "-m", "http.server", str(port)], cwd=directory_path, 
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    try:
        is_windows = os.name == 'nt'
        # Start localtunnel with -y to auto-install and skip prompts
        proc = subprocess.Popen(["npx", "-y", "localtunnel", "--port", str(port)], 
                                stdout=subprocess.PIPE, text=True, shell=is_windows)
        
        # Wait for the URL to appear in stdout
        for _ in range(40): # 20 second timeout
            line = proc.stdout.readline()
            if line and "url is:" in line.lower():
                url = line.split("is:")[1].strip()
                return f"PUBLIC_URL:{url}"
            time.sleep(0.5)
        
        return "Error: Localtunnel timed out. Make sure 'localtunnel' is accessible via npx."
    except Exception as e:
        return f"Error starting host: {str(e)}"
