import re

with open('crunchbase_tracker_cloud.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the Prompt
old_prompt = """    You are a ruthless UAE IT Lead Generation Data Scientist working in April 2026.
    CRITICAL MISSION: Extract ONLY private UAE startup/company funding rounds from the text below.
    ABSOLUTE REJECTIONS:
    - If the company is an accelerator program, a government entity, an incubator, a university, a conference, or a VC firm, RETURN CONFIDENCE SCORE 0.
    - If the text implies a general news compilation or market report, RETURN CONFIDENCE SCORE 0.
    - If the company name contains "Hub", "Accelerator", "Chamber", "Government", "Park", RETURN CONFIDENCE SCORE 0."""

new_prompt = """    You are a ruthless UAE IT Lead Generation Data Scientist working in 2026.
    CRITICAL MISSION: Extract ONLY private UAE startup/company funding rounds from the text below.
    ABSOLUTE REJECTIONS:
    - If the company is a government entity, conference, or a VC firm, RETURN CONFIDENCE SCORE 0."""

content = content.replace(old_prompt, new_prompt)

# 2. Update num_niches_to_scan from 15 to 40
content = content.replace('num_niches_to_scan = 15\n    update_agent_status("Hunting Leads 🎯")', 
                          'num_niches_to_scan = 40\n    update_agent_status("Hunting Leads 🎯")')

# 3. Rewrite current_niches strictly using regex
niches_pattern = r'current_niches = \[.*?\]'
new_niches = """current_niches = [
        # --- BROAD MARKET SWEEPS ---
        'site:crunchbase.com/organization "Dubai" OR "Abu Dhabi" "Seed" OR "Pre-Seed"',
        'site:crunchbase.com/organization "United Arab Emirates" "Series A"',
        'site:crunchbase.com/organization "UAE" "Series B" OR "Venture Round"',
        'site:crunchbase.com/organization "Dubai" "Angel" OR "Convertible Note"',
        'site:crunchbase.com/organization "Abu Dhabi" "Private Equity" OR "Corporate Round"',
        
        # --- SECTOR SPECIFIC BROAD SWEEPS ---
        'site:crunchbase.com/organization "Dubai" AND ("FinTech" OR "Crypto" OR "Web3" OR "Blockchain")',
        'site:crunchbase.com/organization "UAE" AND ("HealthTech" OR "MedTech" OR "Biotech")',
        'site:crunchbase.com/organization "Abu Dhabi" AND ("EdTech" OR "PropTech" OR "Real Estate")',
        'site:crunchbase.com/organization "Dubai" AND ("AI" OR "Artificial Intelligence" OR "Machine Learning")',
        'site:crunchbase.com/organization "UAE" AND ("SaaS" OR "Cloud" OR "Enterprise Software")',
        'site:crunchbase.com/organization "Dubai" AND ("E-commerce" OR "Marketplace" OR "Retail Tech")',
        'site:crunchbase.com/organization "Abu Dhabi" AND ("CleanTech" OR "Climate" OR "Energy")',
        'site:crunchbase.com/organization "UAE" AND ("Cybersecurity" OR "Security" OR "Privacy")',
        'site:crunchbase.com/organization "Dubai" AND ("Logistics" OR "Supply Chain" OR "Delivery")',
        'site:crunchbase.com/organization "UAE" AND ("HR Tech" OR "LegalTech" OR "InsurTech")',
        
        # --- RECENTLY REFRESHED GOOGLE DORKS (Time-Limited) ---
        'site:crunchbase.com/organization "Dubai" "raised" qdr:m',
        'site:crunchbase.com/organization "Abu Dhabi" "funding" qdr:m',
        'site:crunchbase.com/organization "United Arab Emirates" "investment" qdr:m',
        'site:crunchbase.com/organization "UAE" "stealth" qdr:m',
        'site:crunchbase.com/organization "Dubai" "venture capital" qdr:m',
        
        # --- HIGH-GROWTH SPECIFIC ---
        'site:crunchbase.com/organization "Dubai" "autonomous" OR "robotics"',
        'site:crunchbase.com/organization "UAE" "telehealth" OR "virtual care"',
        'site:crunchbase.com/organization "Abu Dhabi" "quantum computing"',
        'site:crunchbase.com/organization "Dubai" "creator economy"',
        'site:crunchbase.com/organization "UAE" "agritech" OR "vertical farming"',
        
        # --- OPEN NET ---
        'site:wamda.com "funded" "Dubai" OR "Abu Dhabi"',
        'site:magnitt.com "raised" "UAE"',
        'site:gulfnews.com "startup" "raised" "Dubai"'
    ]"""

content = re.sub(niches_pattern, new_niches, content, flags=re.DOTALL)

with open('crunchbase_tracker_cloud.py', 'w', encoding='utf-8') as f:
    f.write(content)
