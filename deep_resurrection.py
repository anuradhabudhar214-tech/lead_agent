import subprocess
import csv
import io
import os
from supabase import create_client

def deep_resurrection():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("❌ Credentials missing.")
        return

    client = create_client(url, key)
    
    print("🕰️ Starting Deep Resurrection (Scanning all Git History)...")
    
    try:
        commits = subprocess.check_output(['git', 'log', '--pretty=format:%h', 'enterprise_leads.csv']).decode().split()
    except:
        print("❌ Git history unreachable.")
        return

    all_leads = {} # Map company -> lead data (highest confidence wins)

    for c in commits:
        try:
            data = subprocess.check_output(['git', 'show', f'{c}:enterprise_leads.csv'], stderr=subprocess.DEVNULL).decode(errors='ignore')
            reader = csv.DictReader(io.StringIO(data))
            for row in reader:
                name = row.get("Company") or row.get("company")
                if not name or name == "Filter Out": continue
                name = name.strip()
                
                conf = int(row.get("Confidence") or 85)
                
                # If we don't have this company yet, or this record has better info
                if name not in all_leads or conf > all_leads[name].get('confidence_score', 0):
                    all_leads[name] = {
                        "company": name,
                        "industry": row.get("Industry") or "Technology",
                        "confidence_score": conf,
                        "funding_amount": row.get("Funding Amount") or row.get("Financials") or "Undisclosed",
                        "financials": row.get("Financials") or "Undisclosed",
                        "strategic_signal": row.get("2026 Strategic Signal") or "N/A",
                        "integration_opportunity": row.get("Integration Opportunity") or "N/A",
                        "url": row.get("URL") or "",
                        "discovered_at": "2026-04-16T12:00:00+00:00" # Safe historical date
                    }
        except:
            continue

    leads_list = list(all_leads.values())
    print(f"✨ Reconstructed {len(leads_list)} unique leads from history!")

    print(f"🚀 Pushing to Supabase...")
    for i in range(0, len(leads_list), 20):
        chunk = leads_list[i:i+20]
        try:
            client.table("uae_leads").upsert(chunk, on_conflict="company").execute()
            print(f"✅ Synced block {i//20 + 1}")
        except Exception as e:
            print(f"⚠️ Block Sync failure: {e}")

    print(f"🏁 DONE! Dashboard should now reflect {len(leads_list)} Total Leads.")

if __name__ == "__main__":
    deep_resurrection()
