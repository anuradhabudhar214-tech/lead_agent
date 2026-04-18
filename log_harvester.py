import re
import os

companies = set()
logs = [f for f in os.listdir('.') if f.startswith('full_logs')]

print(f"Scanning {len(logs)} log files...")
for f_path in logs:
    try:
        with open(f_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # Look for the success harvest message
                m = re.search(r'✅ HARVESTED: (.*?) \(Cloud', line)
                if m:
                    companies.add(m.group(1).strip())
    except Exception as e:
        print(f"Error reading {f_path}: {e}")

print(f"Total Unique Companies found in logs: {len(companies)}")
print("Sample list:")
print(", ".join(list(companies)[:15]))

# Save to a temp file for the restorer
with open('reconstructed_companies.txt', 'w', encoding='utf-8') as f:
    for c in sorted(list(companies)):
        f.write(c + '\n')
