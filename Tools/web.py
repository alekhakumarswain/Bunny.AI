import requests
from bs4 import BeautifulSoup
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

def search_web(query: str, max_results: int = 5) -> str:
    """
    Searches the web using Google Custom Search API and returns a list of results.
    Requires GOOGLE_SEARCH_API_KEY and SEARCH_ENGINE_ID in .env file.
    """
    api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
    search_engine_id = os.getenv("SEARCH_ENGINE_ID")

    if not api_key or not search_engine_id:
        return "ERROR: Google Search API credentials (GOOGLE_SEARCH_API_KEY, SEARCH_ENGINE_ID) not found in .env."

    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "q": query,
            "key": api_key,
            "cx": search_engine_id,
            "num": max_results
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        items = data.get("items", [])
        if not items:
            return "No results found."
            
        results = []
        for item in items:
            results.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet")
            })
            
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"ERROR during search: {str(e)}"

def scrape_page(url: str) -> str:
    """
    Reads the content of a specific webpage. 
    Uses Playwright for dynamic/JavaScript websites like Portfolios and SPAs.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "ERROR: Playwright not installed. Use 'scrape_static_page' or install playwright."

    try:
        with sync_playwright() as p:
            # Using a persistent browser to handle some session stuff if needed
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            print(f"  [Dynamic Scraper] Navigating to {url}...")
            # We use a generous timeout and wait for idle network
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Wait a few more seconds for total rendering (for heavy animations)
            time.sleep(3) 
            
            content = page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Remove noise
            for s in soup(["script", "style", "nav", "footer", "iframe"]):
                s.decompose()

            text = soup.get_text(separator=' ')
            lines = (line.strip() for line in text.splitlines())
            clean_text = '\n'.join(line for line in lines if line)
            
            browser.close()
            
            if len(clean_text) < 100:
                return f"Warning: Very little content extracted from {url}. It might be a complex site or bot protected."
                
            return clean_text[:8000]
            
    except Exception as e:
        return f"ERROR scraping dynamic page: {str(e)}"

if __name__ == "__main__":
    # Quick Test
    print("Searching for AI Jobs...")
    print(search_web("recent AI job openings remote"))
