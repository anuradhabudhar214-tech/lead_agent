import re

with open('crunchbase_sweeper.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove Serper keys and search_crunchbase
content = re.sub(r'SERPER_API_KEYS = .*?\n', '', content)
content = re.sub(r'self\.serper_key = .*?\n', '', content)
content = re.sub(r'def search_crunchbase\(self, company\):.*?return " \| "\.join\(all_snippets\)', '', content, flags=re.DOTALL)

# 2. Add Gemini Grounded search to sweeper
new_gemini_search = r"""    def search_crunchbase_grounded(self, company):
        if not self.gemini_key: return ""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
        prompt = f"Search for Crunchbase funding data for {company}. Return a summary of the round and amount."
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"google_search_retrieval": {}}]
        }
        try:
            r = requests.post(url, json=payload, timeout=20)
            return r.json()['candidates'][0]['content']['parts'][0]['text']
        except: return """ + '""'

content = content.replace('def sweep(self):', new_gemini_search + '\n    def sweep(self):')

# 3. Update sweep to use grounded search
content = content.replace('snippets = self.search_crunchbase(company)', 'snippets = self.search_crunchbase_grounded(company)')

with open('crunchbase_sweeper.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Serper REMOVED from Sweeper.")
