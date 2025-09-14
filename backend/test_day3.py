import requests
import json

BASE_URL = "http://localhost:8000/api"

def get_auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": "test@nutrilens.ai", "password": "TestPass123"}
    )
    if response.status_code == 200:
        return response.json()['access_token']
    return None

def test_day3_implementation():
    """Test Day 3 implementation"""
    
    print("🧪 Testing Day 3: Intelligent Item Normalization & Inventory\n")
    
    # Get auth token
    token = get_auth_token()
    if not token:
        print("❌ Failed to authenticate. Please ensure user exists.")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test 1: Add items with various formats
    print("1. Testing intelligent item normalization...")
    test_input = """
    2kg whole wheat flour
    500g chicken breast
    1 litre milk
    3 piece onion
    tomatoes 500g
    panner 200g
    1 dozen eggs
    brocoli 300g
    2 packet maggi noodles
    organic spinach 250g
    basmati rice 5kg
    masoor daal 1kg
    """
    
    response = requests.post(
        f"{BASE_URL}/inventory/add-items",
        json={"text_input": test_input},
        headers=headers
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Item processing complete")
        print(f"   Results: {result['results']['summary']}")
        
        # Show successful items
        if result['results']['successful']:
            print("\n   Successfully added:")
            for item in result['results']['successful'][:3]:
                print(f"   - {item['original']} → {item['matched']} ({item['quantity']}) [Confidence: {item['confidence']:.2f}]")
        
        # Show items needing confirmation
        if result['results']['needs_confirmation']:
            print("\n   Needs confirmation:")
            for item in result['results']['needs_confirmation'][:3]:
                print(f"   - {item['original']} → {item['suggested']} [Confidence: {item['confidence']:.2f}]")
        
        # Show failed items
        if result['results']['failed']:
            print("\n   Failed to identify:")
            for item in result['results']['failed'][:3]:
                print(f"   - {item['original']}: {item['reason']}")
    else:
        print(f"❌ Failed: {response.text}")
    
    # Test 2: Get inventory status
    print("\n2. Testing inventory status with AI insights...")
    response = requests.get(f"{BASE_URL}/inventory/status", headers=headers)
    
    if response.status_code == 200:
        status = response.json()
        print(f"✅ Inventory status retrieved")
        print(f"   Total items: {status['total_items']}")
        print(f"   Total weight: {status['total_weight_g']/1000:.2f}kg")
        print(f"   Days of food remaining: {status['estimated_days_remaining']}")
        print(f"\n   AI Recommendations:")
        for rec in status['ai_recommendations'][:3]:
            print(f"   {rec}")
    else:
        print(f"❌ Failed: {response.text}")
    
    # Test 3: Check makeable recipes
    print("\n3. Testing makeable recipes with current inventory...")
    response = requests.get(
        f"{BASE_URL}/inventory/makeable-recipes",
        headers=headers,
        params={"limit": 5}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Found {result['count']} makeable recipes")
        for recipe in result['recipes'][:3]:
            print(f"   - {recipe['title']} ({recipe.get('prep_time', 0)} min)")
            if 'note' in recipe:
                print(f"     Note: {recipe['note']}")
    else:
        print(f"❌ Failed: {response.text}")
    
    # Test 4: Test specific recipe availability
    print("\n4. Testing recipe availability check...")
    response = requests.get(
        f"{BASE_URL}/inventory/check-recipe/1",
        headers=headers
    )
    
    if response.status_code == 200:
        availability = response.json()
        print(f"✅ Recipe availability checked")
        print(f"   Recipe: {availability.get('recipe', 'Unknown')}")
        print(f"   Can make: {availability['can_make']}")
        print(f"   Coverage: {availability['coverage_percentage']:.1f}%")
        if availability['missing_items']:
            print(f"   Missing: {', '.join([m['item'] for m in availability['missing_items'][:3]])}")
    else:
        print(f"❌ Failed: {response.text}")
    
    # Test 5: Test meal deduction
    print("\n5. Testing meal deduction from inventory...")
    
    # First, let's check if we can make recipe 1
    check_response = requests.get(
        f"{BASE_URL}/inventory/check-recipe/1",
        headers=headers
    )
    
    if check_response.status_code == 200 and check_response.json()['can_make']:
        response = requests.post(
            f"{BASE_URL}/inventory/deduct-meal",
            json={"recipe_id": 1, "portion_multiplier": 1.0},
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Meal ingredients deducted")
            print(f"   Success: {result['success']}")
            if result['deductions']:
                print(f"   Deducted items:")
                for deduction in result['deductions'][:3]:
                    print(f"   - {deduction['item']}: {deduction['deducted']}g (Remaining: {deduction['remaining']}g)")
            if result['warnings']:
                print(f"   Warnings: {', '.join(result['warnings'][:2])}")
        else:
            print(f"❌ Failed: {response.text}")
    else:
        print("⚠️  Cannot make recipe 1 with current inventory")
    
    print("\n✨ Day 3 Testing Complete!")
    print("\n📊 What we've accomplished:")
    print("   - Intelligent item normalization with confidence scoring")
    print("   - Smart unit conversion (kg→g, pieces→weight)")
    print("   - Inventory management with AI insights")
    print("   - Recipe availability checking")
    print("   - Automatic deduction on meal consumption")
    print("\n🎯 The AI can now understand messy human input and manage inventory intelligently!")

if __name__ == "__main__":
    test_day3_implementation()