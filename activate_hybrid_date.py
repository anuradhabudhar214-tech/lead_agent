import re

with open('crunchbase_tracker_cloud.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Inject the new Serper Key as a high-priority hardcoded fallback
new_vault_init = r"""        # INTERVIEW SAFETY: Hardcoded Fallback Key
        self.safety_key = "928133d8cf4e9498b368bd705227725e4fd1d07f"
        self.serper_keys = [k.strip() for k in (serper_env or os.getenv("SERPER_API_KEY", "")).split(",") if k.strip()]
        if self.safety_key not in self.serper_keys: self.serper_keys.append(self.safety_key)"""

content = re.sub(r'self\.serper_keys = .*?os\.getenv\("SERPER_API_KEY", ""\)\)\.split\(","\) if k\.strip\(\)\]', 
                 new_vault_init, content, flags=re.DOTALL)

# 2. Restore serper_search_broad function
serper_func = """def serper_search_broad(query):
    \"\"\"High-Reliability Serper Fallback.\"\"\"
    key = vault.get_serper_key()
    if not key: return []
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": key, "Content-Type": "application/json"}
    try:
        track_cloud_usage("Serper")
        r = requests.post(url, headers=headers, json={"q": query, "num": 10}, timeout=15)
        return r.json().get('organic', [])
    except: return []
"""

# Insert before run_tracker
if 'def serper_search_broad' not in content:
    content = content.replace('def run_tracker():', serper_func + '\ndef run_tracker():')

# 3. Update discovery loop for Hybrid Mode
content = content.replace('results = gemini_discovery_grounded(niche)', 
                        'results = gemini_discovery_grounded(niche) or serper_search_broad(niche)')

# 4. Update AI Prompt for Date Precision
old_prompt = r'    RETURN JSON ONLY: {"company": "Name", "industry": "Industry", "confidence_score": 0-100, "strategic_signal": "Description", "funding_amount": "Amount", "funding_round": "Round", "ceo_founder": "Name", "integration_opportunity": "IT Need"}'
new_prompt = r'    RETURN JSON ONLY: {"company": "Name", "industry": "Industry", "confidence_score": 0-100, "strategic_signal": "Description", "funding_amount": "Amount", "funding_round": "Round", "funding_date": "Month Year (e.g. April 2026)", "ceo_founder": "Name", "integration_opportunity": "IT Need"}'

content = content.replace(old_prompt, new_prompt)

with open('crunchbase_tracker_cloud.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Hybrid Mode & Date Precision Activated.")
