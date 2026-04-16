import requests

keys = ["yD4WPjUpffUdIlSq-Y52xw", "_3nLDK3dz0dAJxW6xkXIiQ", "bzdlDsyOn1EpXSZGAo767g"]

# Test with a well-known UAE company to see if Apollo returns data
test_company = "Careem"

print(f"Testing Apollo for: {test_company}")
for key in keys:
    r = requests.post(
        "https://api.apollo.io/v1/mixed_people/search",
        headers={"Content-Type": "application/json", "X-Api-Key": key},
        json={
            "q_organization_name": test_company,
            "person_titles": ["ceo", "founder", "cto", "managing director"],
            "page": 1,
            "per_page": 3
        },
        timeout=10
    )
    print(f"\nKey: ...{key[-6:]} | HTTP Status: {r.status_code}")
    data = r.json()
    people = data.get("people", [])
    print(f"People found: {len(people)}")
    for p in people:
        print(f"  → {p.get('first_name')} {p.get('last_name')} | {p.get('title')} | Email: {p.get('email')}")
    if r.status_code != 200:
        print(f"Error message: {data.get('message', str(data)[:200])}")
