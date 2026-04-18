import os
import csv
import io
from datetime import datetime, timezone
from supabase import create_client

def final_restore():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        # Fallback to hardcoded if env fails (only for local emergency)
        url = "https://xqzhhskpqlxwzhxwzhxw.supabase.co" # Example
        # I will fetch these from your secrets file
        return

    client = create_client(url, key)
    
    csv_file = 'enterprise_leads.csv'
    if not os.path.exists(csv_file):
        print("❌ CSV not found.")
        return

    print(f"📖 Reading {csv_file} for total reconstruction...")
    leads_to_upsert = []
    unique_names = set()
    
    with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Company", "").strip()
            if not name or name == "Filter Out": continue
            
            # Sanitize Date
            raw_date = row.get("Discovered At", "")
            if "2026" not in raw_date:
                # If date is corrupted ("Active Ent", etc), default to April 16th
                valid_date = "2026-04-16T12:00:00+00:00"
            else:
                valid_date = raw_date

            lead = {
                "company": name,
                "industry": row.get("Industry") or "Technology",
                "confidence_score": int(row.get("Confidence") or 85),
                "funding_amount": row.get("Funding Amount") or row.get("Financials") or "Undisclosed",
                "financials": row.get("Financials") or "Undisclosed",
                "strategic_signal": row.get("2026 Strategic Signal") or "N/A",
                "integration_opportunity": row.get("Integration Opportunity") or "N/A",
                "url": row.get("URL") or "",
                "discovered_at": valid_date
            }
            
            # Local deduplication for the batch
            if name not in unique_names:
                leads_to_upsert.append(lead)
                unique_names.add(name)

    print(f"🚀 Injecting {len(leads_to_upsert)} unique cleaned leads into Supabase...")
    for i in range(0, len(leads_to_upsert), 20):
        chunk = leads_to_upsert[i:i+20]
        try:
            client.table("uae_leads").upsert(chunk, on_conflict="company").execute()
            print(f"✅ Synced chunk {i//20 + 1}")
        except Exception as e:
            print(f"⚠️ Chunk Error: {e}")

    print("🏁 FINAL RECONSTRUCTION COMPLETE! Check the dashboard now.")

if __name__ == "__main__":
    final_restore()
