import re

with open('crunchbase_tracker_cloud.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Increase num_niches_to_scan to 60
content = content.replace('num_niches_to_scan = 40', 'num_niches_to_scan = 60')

# 2. Rewrite niches - Broader, Last 30 Days (qdr:m), No heavy dorks
new_niches_list = """current_niches = [
        # --- PRIMARY STARTUP SWEEPS (Last 30 Days) ---
        'site:crunchbase.com/organization "Dubai" "Seed" OR "Pre-Seed" qdr:m',
        'site:crunchbase.com/organization "Abu Dhabi" "Series A" qdr:m',
        'site:crunchbase.com/organization "UAE" "Venture Round" qdr:m',
        'site:crunchbase.com/organization "Dubai" "FinTech" qdr:m',
        'site:crunchbase.com/organization "Dubai" "AI" OR "SaaS" qdr:m',
        'site:crunchbase.com/organization "UAE" PropTech qdr:m',
        'site:crunchbase.com/organization "Dubai" HealthTech qdr:m',
        'site:crunchbase.com/organization "Abu Dhabi" Logistics qdr:m',
        'site:crunchbase.com/organization "Dubai" E-commerce qdr:m',
        'site:crunchbase.com/organization "UAE" "stealth" qdr:m',
        'site:crunchbase.com/organization "Dubai" "funding" qdr:m',
        'site:crunchbase.com/organization "Abu Dhabi" "investment" qdr:m',
        
        # --- SECTOR TARGETING ---
        'site:crunchbase.com/organization "Dubai" "EdTech" qdr:m',
        'site:crunchbase.com/organization "UAE" "InsurTech" qdr:m',
        'site:crunchbase.com/organization "Dubai" "Cyber" qdr:m',
        'site:crunchbase.com/organization "UAE" "Web3" OR "Crypto" qdr:m',
        'site:crunchbase.com/organization "Dubai" "Robotics" qdr:m',
        'site:crunchbase.com/organization "UAE" "CleanTech" qdr:m',
        'site:crunchbase.com/organization "Dubai" "Gaming" qdr:m',
        'site:crunchbase.com/organization "UAE" "HR Tech" qdr:m',
        
        # --- NEWS SOURCE TRIGGERS ---
        'site:wamda.com "Dubai" OR "Abu Dhabi" 2026 qdr:m',
        'site:magnitt.com "UAE" funding qdr:m',
        'site:entrepreneur.com "startup" Dubai qdr:m',
        'site:gulfnews.com "startup" raised funding qdr:m',
        'site:thenationalnews.com UAE startup funding qdr:m'
    ]"""

# Use regex to find and replace the current_niches block
content = re.sub(r'current_niches = \[.*?\]', new_niches_list, content, flags=re.DOTALL)

# 3. Update the AI Prompt for "Floodgate" mode
old_prompt_re = r'ROLE: Senior UAE Market Intelligence Auditor.*?RETURN JSON ONLY\. No markdown\. No extra text\.'
new_prompt = """    ROLE: Hyper-Scale UAE Lead Generation Agent in April 2026.
    MISSION: Identify private startup funding rounds.
    
    AUDIT RULES:
    1. STARTUP FOCUS: Only accept private companies (Seed, Series A, Venture, etc.).
    2. REJECT: Government, Large Corporates (>1000 employees), Non-Profits.
    3. UAE ONLY: Must be headquartered or have significant operations in UAE.
    4. DATE: Last 30-90 days is acceptable.
    
    RETURN JSON ONLY: {"company": "Name", "industry": "Industry", "confidence_score": 0-100, "strategic_signal": "Description", "funding_amount": "Amount", "funding_round": "Round", "ceo_founder": "Name", "integration_opportunity": "IT Need"}
    If not a UAE startup? Return: {"confidence_score": 0}"""

# Since the prompt might have changed in previous edits, let's find the start of it
content = re.sub(r'prompt = f""".*?"""', f'prompt = f"""{new_prompt}"""', content, flags=re.DOTALL)

with open('crunchbase_tracker_cloud.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Floodgates OPEN: Updated niches and velocity.")
