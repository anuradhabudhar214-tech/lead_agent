import subprocess

def scan():
    try:
        commits = subprocess.check_output(['git', 'log', '--pretty=format:%h', 'enterprise_leads.csv']).decode().split()
        print(f"Scanning {len(commits)} commits...")
        
        results = []
        for c in commits:
            try:
                data = subprocess.check_output(['git', 'show', f'{c}:enterprise_leads.csv'], stderr=subprocess.DEVNULL).decode(errors='ignore')
                rows = data.count('\n')
                results.append((c, rows))
            except:
                continue
        
        # Sort by row count descending
        results.sort(key=lambda x: x[1], reverse=True)
        
        print("\nTop 10 largest backups found:")
        for c, r in results[:10]:
            print(f"Commit {c}: {r} rows")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scan()
