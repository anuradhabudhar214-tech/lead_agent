import re

with open('apollo_enrichment.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove search_serper and related
content = re.sub(r'SERPER_API_KEYS_STR = .*?\n', '', content)
content = re.sub(r'serper_keys = .*?\n', '', content)
content = re.sub(r'serper_idx = 0\n', '', content)
content = re.sub(r'def get_serper_key\(\):.*?def search_serper\(query\):.*?return \[\]', '', content, flags=re.DOTALL)

# 2. Empower Gemini for LinkedIn finding with tools
new_func_body = r"""def ask_gemini_for_linkedin(company_name, company_context=""):
    key = get_gemini_key()
    if not key: return None
    prompt = f"Search for the LinkedIn profile of the CEO or Founder of {company_name}. Return JSON: {{'name': 'Full Name', 'linkedin': 'URL', 'role': 'CEO'}}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search_retrieval": {}}],
        "generationConfig": {"response_mime_type": "application/json"}
    }"""

content = re.sub(r'def ask_gemini_for_linkedin\(company_name, company_context=""\):.*?payload = \{.*?\}', 
                 new_func_body, 
                 content, flags=re.DOTALL)

# 3. Simplify run_enrichment to remove Serper step
content = re.sub(r'# Step 2: Precision Serper Search using Exact Name.*?# Fallback if Serper failed but Gemini guessed a URL', 
                 '# Verification step: Ensure URL is valid', 
                 content, flags=re.DOTALL)

with open('apollo_enrichment.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Serper REMOVED from Enrichment.")
