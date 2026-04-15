import os
from google import genai

def diag():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("NO API KEY FOUND IN ENV")
        return
        
    client = genai.Client(api_key=api_key)
    print("--- Listing Models ---")
    try:
        for model in client.models.list():
            print(f"Name: {model.name}, Actions: {model.supported_generation_methods}")
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    diag()
