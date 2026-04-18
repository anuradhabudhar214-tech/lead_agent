import os
import requests
from supabase import create_client

def verify():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("❌ Missing Supabase Credentials")
        return

    client = create_client(url, key)
    
    # 1. Check Total Count
    res = client.table("uae_leads").select("count", count="exact").execute()
    total = res.count
    
    # 2. Check Today's Count
    today_res = client.table("uae_leads").select("count", count="exact").gte("discovered_at", "2026-04-18").execute()
    today = today_res.count
    
    # 3. Check for Garbage Headlines
    garbage_res = client.table("uae_leads").select("company").ilike("company", "% new member %").execute()
    garbage_found = len(garbage_res.data)

    print(f"📊 DATABASE STATUS:")
    print(f"-------------------")
    print(f"✅ Total Leads: {total}")
    print(f"✅ Found Today: {today}")
    print(f"🚫 Garbage Headlines Left: {garbage_found}")
    print(f"-------------------")
    
    if total > 4:
        print("🚀 SUCCESS: Lead volume is returning!")
    else:
        print("⚠️ WARNING: Total is still low. GHA might still be running...")

if __name__ == "__main__":
    verify()
