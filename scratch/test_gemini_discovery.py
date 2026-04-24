import os
import requests
import json

def test_gemini_discovery():
    api_key = os.getenv("GEMINI_API_KEY") or "YOUR_KEY_HERE"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    prompt = """
    Search for the top 5 newest Crunchbase organization profiles for tech startups in Dubai 
    that raised seed or series funding in the last 30 days. 
    Return the data in the following JSON format: 
    [{"company": "Name", "crunchbase_url": "URL", "funding": "Amount"}]
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search_retrieval": {}}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    
    try:
        r = requests.post(url, json=payload, timeout=30)
        print(f"Status Code: {r.status_code}")
        data = r.json()
        if 'candidates' in data:
            text = data['candidates'][0]['content']['parts'][0]['text']
            print("--- DISCOVERY RESULTS ---")
            print(text)
        else:
            print("Error or No Candidates:")
            print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_gemini_discovery()
