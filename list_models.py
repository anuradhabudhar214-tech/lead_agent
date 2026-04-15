from google import genai
import json

def list_models():
    with open("config.json", "r") as f:
        config = json.load(f)
    
    client = genai.Client(api_key=config["GEMINI_API_KEY"])
    for model in client.models.list():
        print(f"Model ID: {model.name}, Supported Actions: {model.supported_generation_methods}")

if __name__ == "__main__":
    list_models()
