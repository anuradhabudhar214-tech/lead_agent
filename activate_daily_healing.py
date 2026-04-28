import re

with open('crunchbase_tracker_cloud.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Vault with Self-Healing
vault_healing = """    def resurrect_keys(self):
        self.dead_keys = set()
        logger.info("🌤️ TOKEN SELF-HEALING: New day detected. All Gemini/Groq keys resurrected.")
"""
content = content.replace('def get_serper_key(self):', vault_healing + '\n    def get_serper_key(self):')

# 2. Add Daily Sync logic to run_tracker
daily_sync = r"""    # --- DAILY INTELLIGENCE SYNC ---
    now = datetime.now(timezone.utc)
    try:
        stats_res = supabase.table("system_stats").select("*").eq("id", 1).execute()
        if stats_res.data:
            stats = stats_res.data[0]
            last_run_str = stats.get("last_run_at")
            if last_run_str:
                last_dt = datetime.fromisoformat(last_run_str.replace('Z', '+00:00'))
                if last_dt.date() < now.date():
                    logger.info("📅 NEW DAY DETECTED: Resetting Daily Performance Hub...")
                    vault.resurrect_keys()
                    # Reset counters for the new day
                    supabase.table("system_stats").update({
                        "today_scans": 0,
                        "today_leads": 0,
                        "last_run_at": now.isoformat()
                    }).eq("id", 1).execute()
        
        # Calculate Current Today's Leads
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        leads_today = supabase.table("uae_leads").select("id", count="exact").filter("discovered_at", "gte", today_start).execute()
        today_count = leads_today.count or 0
        supabase.table("system_stats").update({"today_leads": today_count}).eq("id", 1).execute()
        logger.info(f"📊 Daily Yield: {today_count} leads harvested today.")
    except Exception as e:
        logger.error(f"Daily Sync Error: {e}")
"""

content = re.sub(r'def run_tracker\(\):', 'def run_tracker():\n' + daily_sync, content)

with open('crunchbase_tracker_cloud.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Daily Stats & Token Self-Healing Active.")
