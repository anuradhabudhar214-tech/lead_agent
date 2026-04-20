import re

with open('crunchbase_tracker_cloud.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Disable catch-up logic overriding velocity
content = re.sub(
    r'if gap_mins > 40:.*?num_niches_to_scan = 10',
    'if gap_mins > 40:\n                        pass',
    content,
    flags=re.DOTALL
)

# 2. Disable Deep Auto-Resurrection
content = re.sub(
    r'# --- DEEP AUTO-RESURRECTION:.*?except Exception as e:\n\s+logger\.warning\(f"Resurrection skip: \{e\}"\)',
    '# --- DEEP AUTO-RESURRECTION DISABLED ---',
    content,
    flags=re.DOTALL
)

# 3. Increase Atomic Velocity to 40
content = re.sub(
    r'# --- ATOMIC VELOCITY BOOST ---\n\s+num_niches_to_scan = 25',
    '# --- ATOMIC VELOCITY BOOST ---\n    num_niches_to_scan = 40',
    content
)

with open('crunchbase_tracker_cloud.py', 'w', encoding='utf-8') as f:
    f.write(content)
