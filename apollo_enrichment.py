import os
import requests
import json
import logging
import time
from datetime import datetime, timezone
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DIAGNOSTICS = []

def _diag(event_type, **kwargs):
    kwargs["type"] = event_type
    kwargs["ts"] = datetime.now(timezone.utc).isoformat()
    DIAGNOSTICS.append(kwargs)

# --- CONFIGURATION ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_API_KEYS_STR = os.environ.get("GEMINI_API_KEYS", "") or os.environ.get("GEMINI_API_KEY", "")
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "https://budhar1.app.n8n.cloud/webhook/9dfb7041-3936-4a0b-a30c-3d3a5a7df4f4")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Supabase credentials missing.")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
gemini_keys = [k.strip() for k in GEMINI_API_KEYS_STR.split(",") if k.strip()]
gemini_idx = 0

def get_gemini_key():
    global gemini_idx
    if not gemini_keys: return None
    key = gemini_keys[gemini_idx % len(gemini_keys)]
    gemini_idx += 1
    return key

def track_cloud_usage(api_name):
    try:
        col = f"{api_name.lower()}_calls"
        res = supabase.table("system_stats").select(f"id, {col}").eq("id", 1).execute()
        if res.data:
            new_val = (res.data[0].get(col) or 0) + 1
            supabase.table("system_stats").update({col: new_val}).eq("id", 1).execute()
    except: pass

def ask_gemini_grounded(prompt, company_name=""):
    """Reliable Gemini Grounded Search."""
    if not gemini_keys:
        _diag("no_gemini_keys", company=company_name)
        return None
    for _ in range(len(gemini_keys) or 1):
        key = get_gemini_key()
        if not key: break

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"google_search_retrieval": {}}],
            "generationConfig": {"response_mime_type": "application/json"}
        }

        try:
            track_cloud_usage("Gemini")
            r = requests.post(url, json=payload, timeout=20)
            res_data = r.json()
            if 'error' in res_data:
                code = res_data['error'].get('code')
                msg = str(res_data['error'].get('message', ''))[:200]
                _diag("gemini_api_error", company=company_name, code=code, message=msg)
                if code in [429, 403]:
                    logger.warning("Gemini quota hit, rotating.")
                    continue
                return None

            if not res_data.get('candidates'):
                _diag("gemini_no_candidates", company=company_name, raw=str(res_data)[:300])
                return None

            text = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
            try:
                return json.loads(text)
            except json.JSONDecodeError as je:
                _diag("gemini_json_parse_fail", company=company_name, error=str(je), raw_text=text[:300])
                return None
        except Exception as e:
            logger.warning(f"Gemini Grounded Search failed: {e}")
            _diag("gemini_request_exception", company=company_name, error=str(e))
            continue
    return None

def notify_n8n(lead, contact_data):
    """Pushes a freshly-found decision maker straight to the n8n webhook for email-find + Slack notify."""
    if not N8N_WEBHOOK_URL:
        return
    try:
        payload = {
            "id": lead.get("id"),
            "company": lead.get("company"),
            "url": lead.get("url"),
            "funding_amount": lead.get("funding_amount"),
            "funding_round": lead.get("funding_round"),
            "strategic_signal": lead.get("strategic_signal"),
            "contact_name": contact_data.get("contact_name"),
            "contact_role": contact_data.get("contact_role", "Founder/CEO"),
            "contact_linkedin": contact_data.get("contact_linkedin")
        }
        requests.post(N8N_WEBHOOK_URL, json=payload, timeout=10)
        logger.info(f"📡 Pushed {lead.get('company')} to n8n webhook")
    except Exception as e:
        logger.warning(f"n8n webhook push failed: {e}")
        _diag("n8n_webhook_fail", company=lead.get("company"), error=str(e))

def enrich_lead(lead, company_name):
    """Finds decision maker LinkedIn and potential email patterns."""
    lead_id = lead["id"]
    logger.info(f"🔎 Enriching: {company_name}")

    prompt = f"""Find the Full Name and LinkedIn profile of the CEO, Founder, or Managing Director of "{company_name}" in the UAE.
Return ONLY a valid JSON object (double-quoted keys and string values, no markdown, no extra text) in exactly this format:
{{"contact_name": "Full Name", "contact_linkedin": "https://www.linkedin.com/in/username", "contact_role": "CEO"}}
If you cannot find a real person, return:
{{"contact_name": null, "contact_linkedin": null, "contact_role": null}}"""

    contact_data = ask_gemini_grounded(prompt, company_name)
    if not contact_data:
        _diag("enrich_no_contact_data", company=company_name)
        return False

    name_found = contact_data.get("contact_name")
    if not name_found:
        _diag("enrich_name_not_found", company=company_name, raw=str(contact_data)[:200])

    # Update lead in DB
    try:
        supabase.table("uae_leads").update({
            "contact_name": contact_data.get("contact_name"),
            "contact_linkedin": contact_data.get("contact_linkedin") or "Not Found",
            "contact_role": contact_data.get("contact_role", "Founder/CEO"),
            "registry_status": "ENRICHED (Gemini Grounding)"
        }).eq("id", lead_id).execute()
        logger.info(f"✅ Enriched: {company_name} -> {contact_data.get('contact_name')}")

        # Push to n8n the moment we have a REAL LinkedIn profile (not a "Not Found" fallback)
        linkedin = contact_data.get("contact_linkedin")
        if linkedin and linkedin != "Not Found":
            notify_n8n(lead, contact_data)

        return True
    except Exception as e:
        logger.error(f"Failed to update lead {lead_id}: {e}")
        _diag("supabase_update_fail", company=company_name, error=str(e))
        return False

def run_enrichment():
    """Fetches leads with missing contact info and enriches them."""
    attempted = 0
    succeeded = 0
    try:
        # Get leads with no contact_name
        res = supabase.table("uae_leads").select("id, company, url, funding_amount, funding_round, strategic_signal").is_("contact_name", "null").limit(6).execute()
        if not res.data:
            logger.info("No leads require enrichment at this time.")
            _diag("no_leads_pending")
            return

        for lead in res.data:
            attempted += 1
            if enrich_lead(lead, lead['company']):
                succeeded += 1
            time.sleep(8) # Stay under free-tier requests-per-minute limit
    except Exception as e:
        logger.error(f"Enrichment Loop Error: {e}")
        _diag("enrichment_loop_exception", error=str(e))
    finally:
        try:
            with open("debug_apollo.json", "w") as f:
                json.dump({
                    "run_at": datetime.now(timezone.utc).isoformat(),
                    "gemini_keys_configured": len(gemini_keys),
                    "attempted": attempted,
                    "succeeded": succeeded,
                    "diagnostics": DIAGNOSTICS,
                    "diagnostics_count": len(DIAGNOSTICS)
                }, f, indent=2)
            logger.info(f"📝 Wrote debug_apollo.json: attempted={attempted}, succeeded={succeeded}, diag_count={len(DIAGNOSTICS)}")
        except Exception as e:
            logger.error(f"Failed to write debug_apollo.json: {e}")

if __name__ == "__main__":
    run_enrichment()
