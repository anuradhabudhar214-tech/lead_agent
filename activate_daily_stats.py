import re

with open('crunchbase_tracker_cloud.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Vault with Self-Healing (reset_daily)
vault_reset_method = """    def reset_daily(self):
        self.dead_keys = set()
        logger.info("🌤️ TOKEN SELF-HEALING: New day detected. All Gemini/Groq keys refreshed.")
"""
content = content.replace('def get_serper_key(self):', vault_reset_method + '\n    def get_serper_key(self):')

# 2. Update run_tracker with Daily Stats logic
daily_logic = r"""    # --- DAILY INTELLIGENCE SYNC ---
    now = datetime.now(timezone.utc)
    try:
        stats_res = supabase.table("system_stats").select("*").eq("id", 1).execute()
        if stats_res.data:
            stats = stats_res.data[0]
            last_run_str = stats.get("last_run_at")
            if last_run_str:
                last_dt = datetime.fromisoformat(last_run_str.replace('Z', '+00:00'))
                # Reset if it's a new day (UTC)
                if last_dt.date() < now.date():
                    logger.info("📅 NEW DAY DETECTED: Resetting Daily Stats...")
                    vault.reset_daily()
                    supabase.table("system_stats").update({
                        "today_scans": 0,
                        "today_leads": 0, # Assuming this column is added or handled
                        "last_run_at": now.isoformat()
                    }).eq("id", 1).execute()
    except Exception as e:
        logger.error(f"Daily Sync Error: {e}")
"""

content = re.sub(r'def run_tracker\(\):', 'def run_tracker():\n' + daily_logic, content)

# 3. Track today_leads when HARVESTED
content = content.replace('save_to_csv(intel)\n                logger.info(f"✅ HARVESTED:', 
                        'save_to_csv(intel)\n                # Update today_leads in DB\n                try: supabase.rpc("increment_today_leads", {"row_id": 1}).execute()\n                except: pass\n                logger.info(f"✅ HARVESTED:')

with open('crunchbase_tracker_cloud.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Daily Stats & Token Self-Healing Active.")
