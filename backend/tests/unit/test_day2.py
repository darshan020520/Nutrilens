#test_day2.py
import requests

BASE_URL = "http://localhost:8000/api"

def safe_get_json(response):
    """Safely parse JSON from response"""
    try:
        return response.json()
    except ValueError:
        print(f"❌ Failed to parse JSON: {response.text}")
        return None

def test_day2_implementation():
    """Test Day 2 implementation"""
    
    print("🧪 Testing Day 2 Implementation...\n")
    
    # Test 1: Check recipe stats
    print("1. Testing recipe statistics...")
    response = requests.get(f"{BASE_URL}/recipes/stats/summary")
    if response.status_code == 200:
        stats = safe_get_json(response)
        if stats:
            print(f"✅ Recipe stats retrieved")
            print(f"   Total recipes: {stats.get('total_recipes', 'N/A')}")
            print(f"   By goal: {stats.get('by_goal', {})}")
            print(f"   By meal time: {stats.get('by_meal_time', {})}")
    else:
        print(f"❌ Failed to get stats: {response.text}")
    
    # Shared function to test recipe listing
    def test_recipe_list(description, params):
        print(f"\n{description}")
        response = requests.get(f"{BASE_URL}/recipes/", params=params)
        if response.status_code == 200:
            recipes = safe_get_json(response)
            if recipes is not None:
                print(f"✅ Found {len(recipes)} recipes")
                if recipes:
                    print(f"   First recipe: {recipes[0].get('title', 'N/A')}")
        else:
            print(f"❌ Failed: {response.text}")
    
    # Test 2: Filtered recipes
    test_recipe_list("2. Testing recipe filtering...", {
        "goal": "muscle_gain",
        "meal_time": "breakfast",
        "limit": 5
    })
    
    # Test 3: Search recipes
    test_recipe_list("3. Testing recipe search...", {
        "search": "chicken",
        "limit": 5
    })
    
    # Test 4: Dietary filtering
    test_recipe_list("4. Testing dietary filtering...", {
        "dietary_type": "vegetarian",
        "limit": 5
    })
    
    # Test 5: Prep time filtering
    test_recipe_list("5. Testing prep time filtering...", {
        "max_prep_time": 15,
        "limit": 5
    })
    
    print("\n✨ Day 2 Testing Complete!")

if __name__ == "__main__":
    test_day2_implementation()
