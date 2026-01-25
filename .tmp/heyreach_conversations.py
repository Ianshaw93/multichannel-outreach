import requests
import os
from dotenv import load_dotenv
import json
import time

load_dotenv()

API_KEY = os.getenv('HEYREACH_API_KEY')
BASE_URL = 'https://api.heyreach.io/api/public'

headers = {
    'X-API-KEY': API_KEY,
    'Content-Type': 'application/json'
}

print("Fetching HeyReach inbox/conversations...")
print("=" * 60)

# First get LinkedIn accounts (senders)
print("\n1. Getting LinkedIn senders...")
time.sleep(0.5)
response = requests.get(f"{BASE_URL}/v2/linkedin-accounts", headers=headers)
print(f"   Status: {response.status_code}")

senders = []
if response.status_code == 200:
    data = response.json()
    print(f"   Found {len(data)} LinkedIn accounts")
    for acc in data:
        sender_id = acc.get('id')
        name = acc.get('firstName', '') + ' ' + acc.get('lastName', '')
        print(f"   - {name} (ID: {sender_id})")
        senders.append(sender_id)

# Now get inbox for each sender
if senders:
    print(f"\n2. Fetching inbox for sender {senders[0]}...")
    time.sleep(0.5)

    # Try to get inbox conversations
    inbox_body = {
        "page": 0,
        "pageSize": 50,
        "linkedInAccountIds": senders[:1],  # Just first sender
        "onlyReplied": True  # Only people who replied
    }

    response = requests.post(
        f"{BASE_URL}/v2/linkedin-accounts/inbox",
        headers=headers,
        json=inbox_body
    )
    print(f"   Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"   Response: {json.dumps(data, indent=2)[:2000]}")

        # Save full response
        with open('.tmp/inbox_response.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("\n   Full response saved to .tmp/inbox_response.json")
    else:
        print(f"   Response: {response.text[:500]}")

        # Try alternative body format
        print("\n   Trying alternative format...")
        time.sleep(0.5)
        response = requests.post(
            f"{BASE_URL}/v2/linkedin-accounts/inbox",
            headers=headers,
            json={"page": 0, "pageSize": 20}
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2)[:2000]}")
        else:
            print(f"   Response: {response.text[:500]}")
