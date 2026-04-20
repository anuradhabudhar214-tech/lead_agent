import os
import csv
import io
import subprocess
from datetime import datetime, timezone
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ MISSION ABORTED: Supabase credentials missing.")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def restore_universal_history():
    print(">>> STARTING UNIVERSAL HISTORY RESTORATION...")
    
    try:
        # 1. Get all commits for the master CSV
        commits = subprocess.check_output(['git', 'log', '--pretty=format:%h', 'enterprise_leads.csv']).decode().split()
        print(f"BACKUP: Found {len(commits)} historical backups to audit.")
        
        all_unique_leads = {}
        
        # 2. Iterate through EVERY commit (no limits)
        for c in commits:
            try:
                data = subprocess.check_output(['git', 'show', f'{c}:enterprise_leads.csv'], stderr=subprocess.DEVNULL).decode(errors='ignore')
                reader = csv.DictReader(io.StringIO(data))
                for row in reader:
                    name = (row.get("Company") or row.get("company") or "").strip()
                    if not name or name == "Filter Out" or len(name) < 2: continue
                    
                    # Store the highest confidence version of each company
                    conf = int(row.get("Confidence") or 85)
                    if name not in all_unique_leads or conf > all_unique_leads[name].get('confidence_score', 0):
                        all_unique_leads[name] = {
                            "company": name,
                            "industry": row.get("Industry") or "Technology",
                            "confidence_score": conf,
                            "funding_amount": row.get("Funding Amount") or row.get("Financials") or "Undisclosed",
                            "strategic_signal": row.get("2026 Strategic Signal") or "N/A",
                            "integration_opportunity": row.get("Integration Opportunity") or "N/A",
                            "url": row.get("URL") or "",
                            "discovered_at": datetime.now(timezone.utc).isoformat()
                        }
            except: continue
        
        print(f"RECOVERED: {len(all_unique_leads)} unique historical leads.")
        
        # 3. Mass Sync to Cloud
        count = 0
        for name, lead in all_unique_leads.items():
            try:
                # Upsert ensures we don't create duplicates
                supabase.table("uae_leads").upsert(lead, on_conflict="company").execute()
                count += 1
                if count % 10 == 0:
                    print(f"SYNCING: {count}/{len(all_unique_leads)}...")
            except Exception as e:
                print(f"ERROR: Error syncing {name}: {e}")
        
        print(f"SUCCESS: {count} leads are now safe in the cloud.")

    except Exception as e:
        print(f"❌ ERROR DURING RESTORATION: {e}")

if __name__ == "__main__":
    restore_universal_history()
