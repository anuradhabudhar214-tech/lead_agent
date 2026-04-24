import re

with open('crunchbase_tracker_cloud.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Vault to handle singular and plural keys
old_vault_init = r'self\.serper_keys = \[k\.strip\(\) for k in serper_env\.split\(","\) if k\.strip\(\)\] or self\.config\.get\("SERPER_API_KEYS", \[\]\)\s+self\.gemini_keys = \[k\.strip\(\) for k in gemini_env\.split\(","\) if k\.strip\(\)\] or self\.config\.get\("GEMINI_API_KEYS", \[\]\)\s+self\.groq_keys = \[k\.strip\(\) for k in groq_env\.split\(","\) if k\.strip\(\)\] or self\.config\.get\("GROQ_API_KEY", \[\]\)'

new_vault_init = """self.serper_keys = [k.strip() for k in (serper_env or os.getenv("SERPER_API_KEY", "")).split(",") if k.strip()] or self.config.get("SERPER_API_KEYS", [])
        self.gemini_keys = [k.strip() for k in (gemini_env or os.getenv("GEMINI_API_KEY", "")).split(",") if k.strip()] or self.config.get("GEMINI_API_KEYS", [])
        self.groq_keys = [k.strip() for k in (groq_env or os.getenv("GROQ_API_KEY", "")).split(",") if k.strip()] or self.config.get("GROQ_API_KEYS", [])"""

content = re.sub(r'self\.serper_keys = .*?self\.groq_keys = .*?\[.*?\]', new_vault_init, content, flags=re.DOTALL)

# 2. Add Gemini Discovery function
gemini_discovery_func = """def gemini_discovery_grounded(query):
    \"\"\"Hyper-accurate IT discovery using Gemini Search Grounding.\"\"\"
    key = vault.get_gemini_key()
    if not key:
        logger.error("No Gemini keys available for discovery!")
        return []
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    
    prompt = f\"\"\"
    You are an IT Market Intelligence Agent. Search for 5 NEW (last 30 days) tech startups or IT companies in the UAE 
    that match this sector: '{query}'. 
    Specifically look for Crunchbase profiles or news of them hiring IT talent.
    
    Return a JSON array of objects:
    [{"title": "Company Name | Signal", "link": "Crunchbase URL", "snippet": "Description of hiring or funding"}]
    \"\"\"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search_retrieval": {}}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    
    try:
        track_cloud_usage("Gemini")
        r = requests.post(url, json=payload, timeout=30)
        data = r.json()
        if 'candidates' in data:
            text = data['candidates'][0]['content']['parts'][0]['text']
            return json.loads(text)
    except Exception as e:
        logger.error(f"⚠️ Gemini Discovery Failed: {e}")
    return []
"""

# Insert before run_tracker
content = content.replace('def run_tracker():', gemini_discovery_func + '\ndef run_tracker():')

# 3. Update niches to IT Sniper mode
new_niches = """current_niches = [
        "Software Development Hiring Dubai",
        "SaaS startups Abu Dhabi hiring",
        "FinTech developers UAE",
        "AI Research Engineers Dubai",
        "Cloud Infrastructure hiring UAE",
        "Cybersecurity startups Dubai",
        "Web3 developers Abu Dhabi",
        "E-commerce tech teams UAE",
        "IT Managed Services hiring Dubai",
        "Data Science startups UAE"
    ]"""

content = re.sub(r'current_niches = \[.*?\]', new_niches, content, flags=re.DOTALL)

# 4. Use Gemini Discovery in the loop
content = content.replace('results = serper_search_broad(niche)', 
                        'results = gemini_discovery_grounded(niche) or serper_search_broad(niche)')

with open('crunchbase_tracker_cloud.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("IT Sniper Mode: Gemini Grounding & Vault Resiliency Active.")
