import os
import json
import time
import logging
import requests
import smtplib
import sys
import re
import csv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from groq import Groq

# Force UTF-8 output for Windows console
try:
    if sys.stdout.encoding.lower() != 'utf-8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tracker.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

CONFIG_FILE = "config.json"
HISTORY_FILE = "history.json"
CSV_MASTER = "enterprise_leads_MASTER.csv"
CSV_VERIFIED = "enterprise_leads_VERIFIED.csv"
URL_FILE = "dashboard_url.json"
STATE_FILE = "agent_state.json"

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except: pass
    return {"seen_urls": [], "current_niche_index": 0, "last_reset_date": datetime.now().strftime("%Y-%m-%d")}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def track_usage(api_name):
    usage_file = "usage.json"
    usage = {"Serper": 0, "Groq": 0}
    if os.path.exists(usage_file):
        try:
            with open(usage_file, "r") as f:
                usage = json.load(f)
        except: pass
    usage[api_name] = usage.get(api_name, 0) + 1
    with open(usage_file, "w") as f:
        json.dump(usage, f)

def update_state(status, current_task):
    state = {"status": status, "current_task": current_task, "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def get_dashboard_link():
    if os.path.exists(URL_FILE):
        try:
            with open(URL_FILE, "r") as f:
                return json.load(f).get("url")
        except: pass
    return "http://localhost:5001"

def save_to_csv(leads, target_file):
    if not leads: return
    file_exists = os.path.isfile(target_file)
    headers = ["Confidence", "Company", "Industry", "Patron/Chairman", "CEO/Founder", "Financials", "2026 Strategic Signal", "Integration Opportunity", "Registry Status", "URL", "Discovered At"]
    try:
        with open(target_file, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if not file_exists: writer.writeheader()
            for lead in leads:
                writer.writerow({
                    "Confidence": lead.get("confidence_score"),
                    "Company": lead.get("company"), 
                    "Industry": lead.get("industry"),
                    "Patron/Chairman": lead.get("patron_chairman"),
                    "CEO/Founder": lead.get("ceo_founder"),
                    "Financials": lead.get("financials"),
                    "2026 Strategic Signal": lead.get("strategic_signal"),
                    "Integration Opportunity": lead.get("integration_opportunity"),
                    "Registry Status": lead.get("registry_status"),
                    "URL": lead.get("url"), 
                    "Discovered At": lead.get("discovered_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
    except Exception as e: logger.error(f"❌ CSV Export Error ({target_file}): {e}")

def send_hourly_report(leads, config):
    if not leads: return
    logger.info("📧 COMPILING HOURLY AUDIT REPORT...")
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"🇦🇪 Auditor Report: {len(leads)} New Intel Signals Found"
    msg['From'] = config["SENDER_EMAIL"]
    msg['To'] = config["RECIPIENT_EMAIL"]
    leads_html = ""
    for lead in leads:
        color = "#10b981" if lead.get('status') == "Active" else "#fbbf24"
        badge = "AUDITED" if lead.get('status') == "Active" else "PENDING"
        leads_html += f"""<div style="margin-bottom: 20px; padding: 15px; border-left: 5px solid {color}; background-color: #f9fafb;">
            <h3 style="margin: 0;">{lead.get('company')} <span style="font-size: 12px; color: {color}; border: 1px solid {color}; padding: 2px 5px; border-radius: 4px;">{badge}</span></h3>
            <p><strong>CEO:</strong> {lead.get('ceo_founder')}</p>
            <p><strong>Confidence:</strong> {lead.get('confidence_score')}%</p>
            <p style="font-size: 14px;">{lead.get('strategic_signal')}</p>
        </div>"""
    html = f"<html><body><h2>Senior Auditor Intelligence Summary</h2>{leads_html}<hr/><p><a href='{get_dashboard_link()}'>View Live Dashboard</a></p></body></html>"
    msg.attach(MIMEText(html, 'html'))
    try:
        with smtplib.SMTP(config["SMTP_SERVER"], config["SMTP_PORT"]) as server:
            server.starttls()
            server.login(config["SENDER_EMAIL"], config["SENDER_PASSWORD"])
            server.send_message(msg)
            logger.info("✅ HOURLY REPORT SENT.")
    except Exception as e: logger.error(f"❌ Email Failed: {e}")

def serper_search(api_key, query, num=5, tbs=None):
    url = "https://google.serper.dev/search"
    headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}
    payload = {"q": query, "num": num}
    if tbs: payload["tbs"] = tbs
    try:
        track_usage("Serper")
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        return response.json().get('organic', [])
    except: return []

def compile_auditor_intel(config, company_name):
    logger.info(f"🕵️ AUDITOR CYCLE: Initiating Truth Filters for '{company_name}'...")
    prompt = f"ROLE: Senior UAE Auditor. OBJ: Verify '{company_name}'. Rules: Zero-Trust Founders, GCC Only, No Rupees, Score 1-100. Min 70. OUT: JSON object."
    try:
        client = Groq(api_key=config.get("GROQ_API_KEY"))
        track_usage("Groq")
        chat_completion = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.3-70b-versatile", response_format={"type": "json_object"})
        data = json.loads(chat_completion.choices[0].message.content)
        if data.get("confidence_score", 0) < 70: return "SKIP" # Audit finished, low score
        return data
    except Exception as e:
        if "429" in str(e) or "limit" in str(e).lower():
            logger.warning(f"⚠️ QUOTA REACHED: Queuing '{company_name}' for next cycle.")
            return "RETRY" # API failed, don't mark as seen
        logger.error(f"❌ Synthesis Error: {e}")
        return "RETRY"

def check_quota_health(config):
    """Checks if Groq is ready to avoid wasting Serper credits."""
    try:
        client = Groq(api_key=config.get("GROQ_API_KEY"))
        client.chat.completions.create(
            messages=[{"role": "user", "content": "hi"}],
            model="llama-3.3-70b-versatile",
            max_tokens=1
        )
        return True
    except Exception as e:
        if "429" in str(e) or "limit" in str(e).lower():
            logger.warning("🛡️ CREDIT BRAKE ACTIVE: Groq Quota Finished. Postponing Serper hunt to save credits.")
            return False
        return True # Other errors might be temporary

def run_tracker():
    config = load_config()
    history = load_history()
    
    # 🛑 CREDIT EMERGENCY BRAKE
    if not check_quota_health(config):
        update_state("Sleeping", "Waiting for Quota Refresh (Credits Saved)")
        return

    update_state("Running", "Rotating Niche Scan")
    niches = config.get("NICHES", [])
    idx = history.get("current_niche_index", 0)
    current_query = niches[idx % len(niches)] if niches else "UAE IT investment 2026"
    logger.info(f"🚀 DIVERSIFIED HUNT: Scanning '{current_query}'")
    
    seen_urls = set(history.get("seen_urls", []))
    raw_results = serper_search(config["SERPER_API_KEY"], current_query, num=10)
    new_items = []
    
    for item in raw_results:
        link = item.get('link')
        if not link or link in seen_urls: continue
        company = item.get('title', '').split("-")[0].strip()
        intel = compile_auditor_intel(config, company)
        
        if isinstance(intel, dict):
            intel['url'], intel['discovered_at'] = link, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_items.append(intel)
            seen_urls.add(link)
            logger.info(f"💎 AUDIT: {company} | Score: {intel.get('confidence_score')}%")
        elif intel == "SKIP":
            seen_urls.add(link)
            logger.info(f"⏭️ SKIPPING: {company} (Low Signal Strength)")
        elif intel == "RETRY":
            logger.info(f"⏳ QUEUED: {company} (Waiting for Quota Refresh)")
            # Do NOT add to seen_urls. Will be found again next cycle.
            continue

    history["seen_urls"] = list(seen_urls)
    history["current_niche_index"] = idx + 1
    save_history(history)

    if new_items:
        # 📂 DUAL-CSV STRATEGY
        save_to_csv(new_items, CSV_MASTER) # Everything to Master
        save_to_csv([i for i in new_items if i.get("status") == "Active"], CSV_VERIFIED) # Only 85%+ to Verified
        
        all_found = []
        if os.path.exists("found_updates.json"):
            try:
                with open("found_updates.json", "r") as f: all_found = json.load(f)
            except: pass
        for lead in reversed(new_items): all_found.insert(0, lead)
        with open("found_updates.json", "w") as f: json.dump(all_found[:50000], f, indent=2)
        send_hourly_report(new_items, config)
    
    update_state("Running", "Sleeping")

if __name__ == "__main__":
    while True:
        try: run_tracker()
        except Exception as e: logger.error(f"🔥 Failure: {e}")
        time.sleep(load_config().get("LOOP_INTERVAL_HOURS", 1) * 3600)
