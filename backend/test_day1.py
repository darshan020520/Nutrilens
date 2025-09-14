import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_day1_implementation():
    """Test Day 1 implementation"""
    
    print("🧪 Testing Day 1 Implementation...\n")
    
    # Test 1: Register a new user
    print("1. Testing user registration...")
    register_data = {
        "email": "test4@nutrilens.ai",
        "password": "TestPass123"
    }
    response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
    if response.status_code == 200:
        print("✅ User registration successful")
        user = response.json()
        print(f"   User ID: {user['id']}")
    else:
        print(f"❌ Registration failed: {response.text}")
        return
    
    # Test 2: Login
    print("\n2. Testing login...")
    login_data = {
        "username": "test@nutrilens.ai",  # OAuth2 uses username field
        "password": "TestPass123"
    }
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data=login_data,  # Form data for OAuth2
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code == 200:
        print("✅ Login successful")
        token_data = response.json()
        access_token = token_data['access_token']
        print(f"   Token: {access_token[:20]}...")
    else:
        print(f"❌ Login failed: {response.text}")
        return
    
    # Test 3: Get current user
    print("\n3. Testing get current user...")
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    if response.status_code == 200:
        print("✅ Get current user successful")
        print(f"   User: {response.json()}")
    else:
        print(f"❌ Get user failed: {response.text}")
    
    # Test 4: Submit basic info
    print("\n4. Testing onboarding - basic info...")
    profile_data = {
        "name": "John Doe",
        "age": 30,
        "height_cm": 175,
        "weight_kg": 75,
        "sex": "male",
        "activity_level": "moderately_active",
        "medical_conditions": []
    }
    response = requests.post(
        f"{BASE_URL}/onboarding/basic-info",
        json=profile_data,
        headers=headers
    )
    if response.status_code == 200:
        print("✅ Profile creation successful")
        profile = response.json()
        print(f"   BMR: {profile['bmr']} cal")
        print(f"   TDEE: {profile['tdee']} cal")
    else:
        print(f"❌ Profile creation failed: {response.text}")
    
    # Test 5: Set goal
    print("\n5. Testing goal selection...")
    goal_data = {
        "goal_type": "muscle_gain",
        "target_weight": 80,
        "macro_targets": {
            "protein": 0.30,
            "carbs": 0.45,
            "fat": 0.25
        }
    }
    response = requests.post(
        f"{BASE_URL}/onboarding/goal-selection",
        json=goal_data,
        headers=headers
    )
    if response.status_code == 200:
        print("✅ Goal selection successful")
        print(f"   Response: {response.json()}")
    else:
        print(f"❌ Goal selection failed: {response.text}")
    
    # Test 6: Set path
    print("\n6. Testing path selection...")
    path_data = {
        "path_type": "traditional"
    }
    response = requests.post(
        f"{BASE_URL}/onboarding/path-selection",
        json=path_data,
        headers=headers
    )
    if response.status_code == 200:
        print("✅ Path selection successful")
        result = response.json()
        print(f"   Meals per day: {result['meals_per_day']}")
    else:
        print(f"❌ Path selection failed: {response.text}")
    
    # Test 7: Set preferences
    print("\n7. Testing preferences...")
    pref_data = {
        "dietary_type": "non_vegetarian",
        "allergies": ["nuts"],
        "disliked_ingredients": ["broccoli"],
        "cuisine_preferences": ["indian", "continental"],
        "max_prep_time_weekday": 30,
        "max_prep_time_weekend": 60
    }
    response = requests.post(
        f"{BASE_URL}/onboarding/preferences",
        json=pref_data,
        headers=headers
    )
    if response.status_code == 200:
        print("✅ Preferences set successful")
    else:
        print(f"❌ Preferences failed: {response.text}")
    
    # Test 8: Get calculated targets
    print("\n8. Testing calculated targets...")
    response = requests.get(
        f"{BASE_URL}/onboarding/calculated-targets",
        headers=headers
    )
    if response.status_code == 200:
        print("✅ Calculated targets retrieved")
        targets = response.json()
        print(f"   Goal Calories: {targets['goal_calories']}")
        print(f"   Macros: {targets['macro_targets']}")
        print(f"   Meal Windows: {len(targets['meal_windows'])} meals")
    else:
        print(f"❌ Get targets failed: {response.text}")
    
    print("\n✨ Day 1 Testing Complete!")

if __name__ == "__main__":
    test_day1_implementation()