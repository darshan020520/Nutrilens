"""
Quick test script for receipt upload
Run this after both services are started
"""
import requests
import json
import os 


# Configuration
BASE_URL = "http://localhost:8000"
SCANNER_URL = "http://host.docker.internal:8001"

# Test 1: Check services are running
print("=" * 80)
print("Testing Receipt Scanner Integration")
print("=" * 80)

print("\n1. Checking Nutrilens backend...")
try:
    response = requests.get(f"{BASE_URL}/health")
    print(f"✅ Nutrilens is running: {response.json()}")
except Exception as e:
    print(f"❌ Nutrilens not reachable: {e}")
    exit(1)

print("\n2. Checking Receipt Scanner...")
try:
    print(f"{SCANNER_URL}/health")
    response = requests.get(f"{SCANNER_URL}/health")
    print(f"✅ Receipt Scanner is running")
except Exception as e:
    print(f"❌ Receipt Scanner not reachable: {e}")
    print("Please start the receipt scanner on port 8001")
    exit(1)

# Test 2: Login to get token
print("\n3. Getting authentication token...")
email = input("Enter your email: ")
password = input("Enter your password: ")

login_response = requests.post(
    f"{BASE_URL}/api/auth/login",
    data={"username": email, "password": password}
)

if login_response.status_code != 200:
    print(f"❌ Login failed: {login_response.json()}")
    exit(1)

token = login_response.json()["access_token"]
print(f"✅ Got authentication token")

# Test 3: Upload receipt
print("\n4. Upload receipt...")
receipt_path = input("Enter path to receipt image: ")

try:
    with open(receipt_path, 'rb') as f:
        files = {'file': f}
        headers = {'Authorization': f'Bearer {token}'}

        print("Uploading receipt (this may take 30-60 seconds)...")
        response = requests.post(
            f"{BASE_URL}/api/receipt/upload",
            files=files,
            headers=headers,
            timeout=120
        )

    if response.status_code == 200:
        result = response.json()
        print("\n✅ Receipt processed successfully!")
        print(f"\nReceipt ID: {result['receipt_id']}")
        print(f"Total items found: {result['total_items']}")
        print(f"Auto-added: {result['auto_added_count']}")
        print(f"Needs confirmation: {result['needs_confirmation_count']}")

        print("\n" + "=" * 80)
        print("AUTO-ADDED ITEMS:")
        print("=" * 80)
        for item in result['auto_added']:
            print(f"✅ {item['item_name']}: {item['quantity_grams']}g (confidence: {item['confidence']:.2f})")

        print("\n" + "=" * 80)
        print("NEEDS CONFIRMATION:")
        print("=" * 80)
        for item in result['needs_confirmation']:
            print(f"⚠️  {item['original_input']}: {item.get('item_name', 'No match')} (confidence: {item['confidence']:.2f})")

    else:
        print(f"\n❌ Upload failed: {response.status_code}")
        print(response.json())

except Exception as e:
    print(f"\n❌ Error during upload: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("Test complete!")
print("=" * 80)
