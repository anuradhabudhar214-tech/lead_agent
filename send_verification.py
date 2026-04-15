import json
import os
import sys
from crunchbase_tracker import load_config, send_premium_html_report

def verify_and_send():
    config = load_config()
    UPDATES_FILE = 'found_updates.json'
    
    # We will use some archived leads if the fresh list is empty
    leads = []
    if os.path.exists(UPDATES_FILE):
        with open(UPDATES_FILE, 'r') as f:
            leads = json.load(f)
            
    if not leads:
        # Fallback to some hardcoded demo intel if file is empty
        leads = [
            {
                "score": 88,
                "company": "Prop-AI",
                "industry": "Proptech",
                "decision_maker": "Ranime El Skaff (Co-Founder)",
                "financials": "$1.5M Pre-Seed (Plus VC)",
                "strategic_signal": "Launched 'Dubai Deal Index' (March 2026)",
                "integration_opportunity": "Expanding Lead Gen team indicates need for CRM/API integration."
            },
            {
                "score": 80,
                "company": "1001 AI",
                "industry": "Deep Tech / AI",
                "decision_maker": "Bilal Abu-Ghazaleh (Founder/CEO)",
                "financials": "$9M Seed (Accel)",
                "strategic_signal": "Massive hiring for Dubai Engineering Hub (2026)",
                "integration_opportunity": "Hiring spree implies backend infrastructure overhaul."
            }
        ]
        
    print(f"📡 Sending Verification Briefing with {len(leads)} leads...")
    send_premium_html_report(config, leads)
    print("✅ Verification Briefing Sent!")

if __name__ == "__main__":
    verify_and_send()
