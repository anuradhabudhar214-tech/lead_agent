import os
import requests

def force_zero_reset():
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Missing API Keys")
        return

    url = f"{SUPABASE_URL}/rest/v1/system_stats"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    # FORCE ZERO EVERYTHING
    data = {
        "gemini_calls": 0,
        "groq_calls": 0,
        "today_scans": 0,
        "serper_calls": 0 # Starting fresh for Serper too
    }
    
    try:
        r = requests.patch(url, headers=headers, params={"id": "eq.1"}, json=data)
        if r.status_code in [200, 201, 204]:
            print("✅ DATABASE MANUALLY ZEROED OUT - FRESH START")
        else:
            print(f"❌ Reset Failed: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"💥 Critical Error: {e}")

if __name__ == "__main__":
    force_zero_reset()
