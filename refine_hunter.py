import re

with open('crunchbase_tracker_cloud.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Broaden the exclusion list in the "clean_company_name" function as a second layer
old_rejections = "rejection_keywords = \["
new_rejections = "rejection_keywords = ['ADGM', 'DIFC', 'Mubadala', 'ADIA', 'Authority', 'Government', 'Foundation', 'Chamber', "

content = content.replace(old_rejections, new_rejections)

# 2. Rewrite niches with NEGATIVE DORKS
exclusion_dork = ' -Government -Authority -Chamber -Foundation -ADGM -DIFC -Park -Mubadala -Hub71 -ADIA'

new_niches_list = f"""current_niches = [
        # --- FRESH STARTUP SIGNALS (Targeting 2026) ---
        'site:crunchbase.com/organization "Dubai" "Seed" OR "Pre-Seed" 2026{exclusion_dork}',
        'site:crunchbase.com/organization "Abu Dhabi" "Series A" 2026{exclusion_dork}',
        'site:crunchbase.com/organization "UAE" "Venture Round" 2026{exclusion_dork}',
        'site:crunchbase.com/organization "Dubai" "FinTech" "Seed" 2026{exclusion_dork}',
        'site:crunchbase.com/organization "UAE" "AI" "Aura" OR "Aya" OR "Ray" 2026{exclusion_dork}',
        
        # --- HIGH PROBABILITY TECH (SME Scale) ---
        'site:crunchbase.com/organization "Dubai" SaaS "funding" 2026{exclusion_dork}',
        'site:crunchbase.com/organization "UAE" PropTech "raised" 2026{exclusion_dork}',
        'site:crunchbase.com/organization "Dubai" HealthTech "seed" 2026{exclusion_dork}',
        'site:crunchbase.com/organization "Abu Dhabi" Logistics "Series A" 2026{exclusion_dork}',
        'site:crunchbase.com/organization "UAE" E-commerce "funding" 2026{exclusion_dork}',
        
        # --- RECENTLY DISCOVERED NEWS (Last 30 Days) ---
        'site:wamda.com "funded" UAE 2026 qdr:m',
        'site:magnitt.com "invested" Dubai 2026 qdr:m',
        'site:entrepreneur.com "startup" Abu Dhabi 2026 qdr:m',
        'site:crunchbase.com/organization "Dubai" "stealth" 2026{exclusion_dork}',
        'site:crunchbase.com/organization "UAE" "stealth mode" 2026{exclusion_dork}',
        
        # --- BROADENING SEARCH OPERATORS ---
        'site:crunchbase.com/organization "Dubai" AND ("Cyber" OR "Crypto" OR "Web3") 2026{exclusion_dork}',
        'site:crunchbase.com/organization "UAE" AND ("EdTech" OR "InsurTech" OR "LegalTech") 2026{exclusion_dork}',
        'site:crunchbase.com/organization "Dubai" AND ("HR" OR "Gaming" OR "Retail") 2026{exclusion_dork}',
        'site:crunchbase.com/organization "Abu Dhabi" AND ("CleanTech" OR "Climate" OR "Water") 2026{exclusion_dork}',
        'site:crunchbase.com/organization "Dubai" AND ("Robotics" OR "Drones" OR "Mobility") 2026{exclusion_dork}'
    ]"""

# Use regex to find and replace the current_niches block
content = re.sub(r'current_niches = \[.*?\]', new_niches_list, content, flags=re.DOTALL)

with open('crunchbase_tracker_cloud.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated crunchbase_tracker_cloud.py with Excellence-grade targeting.")
