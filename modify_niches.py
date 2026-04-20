import re

with open('crunchbase_tracker_cloud.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace all 2024/2025 with 2026 in the file
text = text.replace('2024', '2026').replace('2025', '2026')

with open('crunchbase_tracker_cloud.py', 'w', encoding='utf-8') as f:
    f.write(text)
