import json
import requests
import sys

def search_ceo(company_name):
    # Dummy config or load from config.json
    with open("config.json", "r") as f:
        config = json.load(f)
        
    url = "https://google.serper.dev/search"
    payload = json.dumps({
        "q": f"{company_name} UAE CEO OR Founder \"email\"",
        "num": 3
    })
    headers = {
        'X-API-KEY': config["SERPER_API_KEY"],
        'Content-Type': 'application/json'
    }
    
    response = requests.request("POST", url, headers=headers, data=payload)
    print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    search_ceo("Presight")
