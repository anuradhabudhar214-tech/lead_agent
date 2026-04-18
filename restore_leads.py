import os
import csv
import subprocess
from supabase import create_client

def restore():
    # 1. Get credentials
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("❌ Missing Supabase Credentials. Cannot restore.")
        return

    client = create_client(url, key)
    
    # 2. Extract old CSV from Git (Commit 47a4d22 is from April 17)
    try:
        print("💾 Extracting backup from Git history...")
        old_csv = subprocess.check_output(["git", "show", "47a4d22:enterprise_leads.csv"]).decode('utf-8')
        reader = csv.DictReader(old_csv.splitlines())
    except Exception as e:
        print(f"❌ Failed to extract git backup: {e}")
        return

    # 3. Map CSV to DB Columns
    leads_to_insert = []
    for row in reader:
        lead = {
            "company": row.get("Company"),
            "industry": row.get("Industry"),
            "confidence_score": int(row.get("Confidence", 80)),
            "funding_amount": row.get("Financials", "Undisclosed"),
            "financials": row.get("Financials"),
            "strategic_signal": row.get("2026 Strategic Signal"),
            "integration_opportunity": row.get("Integration Opportunity"),
            "patron_chairman": row.get("Patron/Chairman"),
            "ceo_founder": row.get("CEO/Founder"),
            "registry_status": row.get("Registry Status"),
            "url": row.get("URL"),
            "discovered_at": row.get("Discovered At")
        }
        leads_to_insert.append(lead)

    # 4. Upsert to Supabase
    print(f"🚀 Restoring {len(leads_to_insert)} leads...")
    for i in range(0, len(leads_to_insert), 50):
        chunk = leads_to_insert[i:i+50]
        try:
            client.table("uae_leads").upsert(chunk, on_conflict="company").execute()
            print(f"✅ Restored chunk {i//50 + 1}")
        except Exception as e:
            print(f"⚠️ Chunk failure: {e}")

    print("🏁 Restoration Complete! Check the dashboard.")

if __name__ == "__main__":
    restore()
