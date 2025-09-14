import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session
from app.models.database import *
from app.core.config import settings
import json
from datetime import datetime
from tabulate import tabulate  # Fixed import

def json_serializer(obj):
    """JSON serializer for objects not serializable by default"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)

def inspect_database():
    """Comprehensive database inspection"""
    engine = create_engine(settings.database_url)
    inspector = inspect(engine)
    
    print("=" * 80)
    print("🔍 NUTRILENS DATABASE INSPECTION REPORT")
    print("=" * 80)
    print(f"Database URL: {settings.database_url.split('@')[1] if '@' in settings.database_url else settings.database_url}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 80)
    
    # Get all tables
    tables = inspector.get_table_names()
    print(f"\n📊 Total Tables Found: {len(tables)}")
    print("-" * 40)
    
    with Session(engine) as session:
        # 1. Users Table
        print("\n👤 USERS TABLE:")
        users = session.query(User).all()
        if users:
            user_data = []
            for user in users:
                user_data.append([
                    user.id,
                    user.email,
                    user.is_active,
                    user.created_at.strftime("%Y-%m-%d %H:%M") if user.created_at else None,
                    user.last_login.strftime("%Y-%m-%d %H:%M") if user.last_login else None
                ])
            print(tabulate(
                user_data,
                headers=["ID", "Email", "Active", "Created At", "Last Login"],
                tablefmt="grid"
            ))
        else:
            print("  ❌ No users found")
        print(f"  Total Users: {len(users)}")
        
        # 2. User Profiles
        print("\n📋 USER PROFILES:")
        profiles = session.query(UserProfile).all()
        if profiles:
            profile_data = []
            for prof in profiles:
                profile_data.append([
                    prof.id,
                    prof.user_id,
                    prof.name,
                    prof.age,
                    f"{prof.height_cm}cm",
                    f"{prof.weight_kg}kg",
                    prof.sex,
                    prof.activity_level.value if prof.activity_level else None,
                    f"{prof.bmr:.2f}" if prof.bmr else None,
                    f"{prof.tdee:.2f}" if prof.tdee else None,
                    f"{prof.goal_calories:.2f}" if prof.goal_calories else None
                ])
            print(tabulate(
                profile_data,
                headers=["ID", "User", "Name", "Age", "Height", "Weight", "Sex", "Activity", "BMR", "TDEE", "Goal Cal"],
                tablefmt="grid"
            ))
        else:
            print("  ❌ No profiles found")
        print(f"  Total Profiles: {len(profiles)}")
        
        # 3. User Goals
        print("\n🎯 USER GOALS:")
        goals = session.query(UserGoal).all()
        if goals:
            goal_data = []
            for goal in goals:
                goal_data.append([
                    goal.id,
                    goal.user_id,
                    goal.goal_type.value if goal.goal_type else None,
                    goal.target_weight,
                    json.dumps(goal.macro_targets, indent=0) if goal.macro_targets else None,
                    goal.is_active
                ])
            print(tabulate(
                goal_data,
                headers=["ID", "User", "Goal Type", "Target Weight", "Macros", "Active"],
                tablefmt="grid"
            ))
        else:
            print("  ❌ No goals found")
        print(f"  Total Goals: {len(goals)}")
        
        # 4. User Paths
        print("\n🍽️ USER PATHS:")
        paths = session.query(UserPath).all()
        if paths:
            path_data = []
            for path in paths:
                path_data.append([
                    path.id,
                    path.user_id,
                    path.path_type.value if path.path_type else None,
                    path.meals_per_day,
                    len(path.meal_windows) if path.meal_windows else 0
                ])
            print(tabulate(
                path_data,
                headers=["ID", "User", "Path Type", "Meals/Day", "Windows"],
                tablefmt="grid"
            ))
            
            # Show meal windows detail
            for path in paths:
                if path.meal_windows:
                    print(f"\n  User {path.user_id} Meal Windows:")
                    for window in path.meal_windows:
                        print(f"    - {window['meal']}: {window['start_time']} - {window['end_time']}")
        else:
            print("  ❌ No paths found")
        print(f"  Total Paths: {len(paths)}")
        
        # 5. User Preferences
        print("\n🥗 USER PREFERENCES:")
        prefs = session.query(UserPreference).all()
        if prefs:
            pref_data = []
            for pref in prefs:
                pref_data.append([
                    pref.id,
                    pref.user_id,
                    pref.dietary_type.value if pref.dietary_type else None,
                    ", ".join(pref.allergies) if pref.allergies else "None",
                    ", ".join(pref.cuisine_preferences) if pref.cuisine_preferences else "None",
                    f"{pref.max_prep_time_weekday}min",
                    f"{pref.max_prep_time_weekend}min"
                ])
            print(tabulate(
                pref_data,
                headers=["ID", "User", "Diet", "Allergies", "Cuisines", "Weekday", "Weekend"],
                tablefmt="grid"
            ))
        else:
            print("  ❌ No preferences found")
        print(f"  Total Preferences: {len(prefs)}")
        
        # 6. Items (Food Database)
        print("\n🍎 ITEMS (Food Database):")
        items = session.query(Item).all()
        print(f"  Total Items: {len(items)}")
        if items and len(items) <= 10:  # Show first 10 if exists
            item_data = []
            for item in items[:10]:
                item_data.append([
                    item.id,
                    item.canonical_name,
                    item.category,
                    item.unit,
                    "Yes" if item.nutrition_per_100g else "No"
                ])
            print(tabulate(
                item_data,
                headers=["ID", "Name", "Category", "Unit", "Nutrition"],
                tablefmt="grid"
            ))
        elif items:
            print(f"  (Showing count only - {len(items)} items exist)")
        
        # 7. Recipes
        print("\n🍳 RECIPES:")
        recipes = session.query(Recipe).all()
        print(f"  Total Recipes: {len(recipes)}")
        if recipes and len(recipes) <= 10:
            recipe_data = []
            for recipe in recipes[:10]:
                recipe_data.append([
                    recipe.id,
                    recipe.title[:30],
                    recipe.cuisine,
                    f"{recipe.prep_time_min}min" if recipe.prep_time_min else "N/A",
                    recipe.servings
                ])
            print(tabulate(
                recipe_data,
                headers=["ID", "Title", "Cuisine", "Prep Time", "Servings"],
                tablefmt="grid"
            ))
        
        # 8. User Inventory
        print("\n📦 USER INVENTORY:")
        inventory = session.query(UserInventory).all()
        print(f"  Total Inventory Items: {len(inventory)}")
        
        # 9. Meal Plans
        print("\n📅 MEAL PLANS:")
        meal_plans = session.query(MealPlan).all()
        print(f"  Total Meal Plans: {len(meal_plans)}")
        
        # 10. Meal Logs
        print("\n📝 MEAL LOGS:")
        meal_logs = session.query(MealLog).all()
        print(f"  Total Meal Logs: {len(meal_logs)}")
        
        # Summary Statistics
        print("\n" + "=" * 80)
        print("📊 SUMMARY STATISTICS")
        print("=" * 80)
        
        # Check for data consistency issues
        print("\n⚠️  POTENTIAL ISSUES:")
        issues = []
        
        # Check for duplicate users
        user_emails = [u.email for u in users]
        if len(user_emails) != len(set(user_emails)):
            issues.append("❌ Duplicate user emails detected")
            duplicate_emails = [email for email in user_emails if user_emails.count(email) > 1]
            print(f"  Duplicate emails: {set(duplicate_emails)}")
        
        # Check for orphaned profiles
        user_ids = [u.id for u in users]
        orphaned_profiles = [p for p in profiles if p.user_id not in user_ids]
        if orphaned_profiles:
            issues.append(f"❌ {len(orphaned_profiles)} orphaned profiles found")
        
        # Check for users without complete onboarding
        for user in users:
            has_profile = any(p.user_id == user.id for p in profiles)
            has_goal = any(g.user_id == user.id for g in goals)
            has_path = any(p.user_id == user.id for p in paths)
            has_pref = any(p.user_id == user.id for p in prefs)
            
            if not all([has_profile, has_goal, has_path, has_pref]):
                missing = []
                if not has_profile: missing.append("profile")
                if not has_goal: missing.append("goal")
                if not has_path: missing.append("path")
                if not has_pref: missing.append("preferences")
                issues.append(f"⚠️  User {user.id} ({user.email}) missing: {', '.join(missing)}")
        
        if not issues:
            print("  ✅ No issues detected")
        else:
            for issue in issues:
                print(f"  {issue}")
        
        # Database size info
        print("\n📈 DATABASE METRICS:")
        with engine.connect() as conn:
            # Get database size (PostgreSQL specific)
            try:
                result = conn.execute(text("""
                    SELECT 
                        pg_database.datname,
                        pg_size_pretty(pg_database_size(pg_database.datname)) AS size
                    FROM pg_database
                    WHERE datname = current_database()
                """))
                for row in result:
                    print(f"  Database Size: {row[1]}")
            except:
                print("  Database Size: Unable to determine")
            
            # Table sizes
            print("\n  Table Sizes:")
            try:
                result = conn.execute(text("""
                    SELECT
                        relname AS table_name,
                        pg_size_pretty(pg_total_relation_size(relid)) AS size,
                        n_tup_ins AS inserts,
                        n_tup_upd AS updates,
                        n_tup_del AS deletes
                    FROM pg_stat_user_tables
                    ORDER BY pg_total_relation_size(relid) DESC
                    LIMIT 10
                """))
                
                table_stats = []
                for row in result:
                    table_stats.append(list(row))
                
                if table_stats:
                    print(tabulate(
                        table_stats,
                        headers=["Table", "Size", "Inserts", "Updates", "Deletes"],
                        tablefmt="grid"
                    ))
            except:
                print("  Unable to get table statistics")
        
        print("\n" + "=" * 80)
        print("🏁 INSPECTION COMPLETE")
        print("=" * 80)

def check_relationships():
    """Check all foreign key relationships"""
    engine = create_engine(settings.database_url)
    
    print("\n" + "=" * 80)
    print("🔗 RELATIONSHIP VALIDATION")
    print("=" * 80)
    
    with Session(engine) as session:
        # Check each user's related data
        users = session.query(User).all()
        
        for user in users:
            print(f"\n👤 User {user.id} ({user.email}):")
            
            # Check profile
            profile = session.query(UserProfile).filter(UserProfile.user_id == user.id).first()
            print(f"  Profile: {'✅ Yes' if profile else '❌ No'}")
            if profile:
                print(f"    - Name: {profile.name}")
                print(f"    - BMR: {profile.bmr}")
                print(f"    - TDEE: {profile.tdee}")
                print(f"    - Goal Calories: {profile.goal_calories}")
            
            # Check goal
            goal = session.query(UserGoal).filter(UserGoal.user_id == user.id).first()
            print(f"  Goal: {'✅ Yes' if goal else '❌ No'}")
            if goal:
                print(f"    - Type: {goal.goal_type.value if goal.goal_type else 'None'}")
                print(f"    - Macros: {goal.macro_targets}")
            
            # Check path
            path = session.query(UserPath).filter(UserPath.user_id == user.id).first()
            print(f"  Path: {'✅ Yes' if path else '❌ No'}")
            if path:
                print(f"    - Type: {path.path_type.value if path.path_type else 'None'}")
                print(f"    - Meals/Day: {path.meals_per_day}")
            
            # Check preferences
            pref = session.query(UserPreference).filter(UserPreference.user_id == user.id).first()
            print(f"  Preferences: {'✅ Yes' if pref else '❌ No'}")
            if pref:
                print(f"    - Diet: {pref.dietary_type.value if pref.dietary_type else 'None'}")
                print(f"    - Allergies: {pref.allergies}")

def cleanup_duplicate_users():
    """Optional: Clean up duplicate user entries"""
    engine = create_engine(settings.database_url)
    
    print("\n" + "=" * 80)
    print("🧹 CLEANUP DUPLICATE USERS")
    print("=" * 80)
    
    with Session(engine) as session:
        # Find duplicate emails
        users = session.query(User).order_by(User.created_at).all()
        email_to_users = {}
        
        for user in users:
            if user.email not in email_to_users:
                email_to_users[user.email] = []
            email_to_users[user.email].append(user)
        
        # Report duplicates
        duplicates_found = False
        for email, user_list in email_to_users.items():
            if len(user_list) > 1:
                duplicates_found = True
                print(f"\n📧 Email: {email}")
                print(f"  Found {len(user_list)} accounts:")
                for u in user_list:
                    profile = session.query(UserProfile).filter(UserProfile.user_id == u.id).first()
                    print(f"    - User ID {u.id}: created {u.created_at}, has_profile: {bool(profile)}")
                
                # Keep the one with most complete data or newest
                keeper = max(user_list, key=lambda x: (
                    bool(session.query(UserProfile).filter(UserProfile.user_id == x.id).first()),
                    x.created_at or datetime.min
                ))
                print(f"  ✅ Keeping User ID {keeper.id}")
                
                # Note: Actual deletion commented out for safety
                # for u in user_list:
                #     if u.id != keeper.id:
                #         print(f"  🗑️ Would delete User ID {u.id}")
                #         # session.delete(u)
        
        if not duplicates_found:
            print("\n✅ No duplicate users found!")
        else:
            print("\n⚠️  Duplicates found but not deleted (uncomment code to enable)")
        
        # session.commit()  # Uncomment if actually deleting

if __name__ == "__main__":
    print("\n🚀 Starting NutriLens Database Inspection...\n")
    
    # Run inspections
    inspect_database()
    check_relationships()
    cleanup_duplicate_users()
    
    print("\n✅ Inspection Complete!\n")