import requests
import os
import base64
import json
from nacl import encoding, public

# --- CONFIG ---
GH_PAT = os.environ.get("GH_PAT", "")
REPO = "anuradhabudhar214-tech/lead_agent"
APOLLO_KEYS = "yD4WPjUpffUdIlSq-Y52xw,_3nLDK3dz0dAJxW6xkXIiQ,bzdlDsyOn1EpXSZGAo767g"

def get_repo_public_key():
    url = f"https://api.github.com/repos/{REPO}/actions/secrets/public-key"
    headers = {"Authorization": f"Bearer {GH_PAT}", "Accept": "application/vnd.github+json"}
    r = requests.get(url, headers=headers)
    return r.json()

def encrypt_secret(public_key_str, secret_value):
    pk = public.PublicKey(public_key_str.encode("utf-8"), encoding.Base64Encoder)
    sealed = public.SealedBox(pk)
    encrypted = sealed.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")

def set_secret(name, value, key_id, encrypted_val):
    url = f"https://api.github.com/repos/{REPO}/actions/secrets/{name}"
    headers = {"Authorization": f"Bearer {GH_PAT}", "Accept": "application/vnd.github+json"}
    data = {"encrypted_value": encrypted_val, "key_id": key_id}
    r = requests.put(url, headers=headers, json=data)
    print(f"Set secret {name}: {r.status_code}")

if not GH_PAT:
    print("GH_PAT not set. Skipping GitHub secret upload.")
    print("Apollo keys are embedded directly in apollo_enrichment.py as fallback.")
else:
    key_data = get_repo_public_key()
    key_id = key_data["key_id"]
    pub_key = key_data["key"]
    encrypted = encrypt_secret(pub_key, APOLLO_KEYS)
    set_secret("APOLLO_API_KEYS", APOLLO_KEYS, key_id, encrypted)
    print("Apollo keys successfully added to GitHub Secrets!")
