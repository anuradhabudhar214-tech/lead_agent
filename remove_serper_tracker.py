import re

with open('crunchbase_tracker_cloud.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove Serper from Vault
content = re.sub(r'serper_env = .*?\n', '', content)
content = re.sub(r'self\.serper_keys = .*?\n', '', content)
content = re.sub(r'self\.serper_idx = 0\n', '', content)
content = re.sub(r'def get_serper_key\(self\):.*?def rotate_serper\(self\):.*?\n\s+logger\.info\(f"ð\x9f\x94\x84 Rotated Serper Key"\)', '', content, flags=re.DOTALL)

# 2. Remove serper_search_broad function
content = re.sub(r'def serper_search_broad\(query\):.*?return \[\]', '', content, flags=re.DOTALL)

# 3. Simplify the discovery loop to use ONLY Gemini Grounding
content = content.replace('results = gemini_discovery_grounded(niche) or serper_search_broad(niche)', 
                        'results = gemini_discovery_grounded(niche)')

# 4. Remove Serper from status cleanup logic
content = content.replace('if last_dt.month < now.month or last_dt.year < now.year: data.update({"serper_calls": 0})', '')

with open('crunchbase_tracker_cloud.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Serper REMOVED from Tracker.")
