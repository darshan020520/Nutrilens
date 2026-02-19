#!/usr/bin/env python3
"""
NutriLens AI Safe Database Seeder
ONLY adds new data - NEVER deletes anything
"""

import sys
import os
from pathlib import Path

# Add backend to Python path


import argparse
from app.models.database import SessionLocal, engine, Base
from app.models.database import Recipe, RecipeIngredient, Item
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SafeDatabaseManager:
    """Safe database manager - ONLY creates and adds data, never deletes"""
    
    def __init__(self):
        self.engine = engine
        self.db = SessionLocal()
    
    def create_tables_if_needed(self):
        """Create database tables if they don't exist"""
        logger.info("Ensuring database tables exist...")
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables ready")
    
    def check_data_status(self):
        """Check current database status"""
        try:
            recipe_count = self.db.query(Recipe).count()
            item_count = self.db.query(Item).count()
            ingredient_count = self.db.query(RecipeIngredient).count()
            
            logger.info("Current Database Status:")
            logger.info(f"- Recipes: {recipe_count}")
            logger.info(f"- Food Items: {item_count}")
            logger.info(f"- Recipe-Ingredient Links: {ingredient_count}")
            
            return {
                'recipes': recipe_count,
                'items': item_count,
                'ingredients': ingredient_count
            }
        except Exception as e:
            logger.error(f"Error checking database status: {e}")
            return None
    
    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()

def run_safe_seeder():
    """Import and run the safe incremental seeder"""
    try:
        from seed_data import NutriLensSeeder
        seeder = NutriLensSeeder()
        seeder.run_incremental_seed()
        return True
    except Exception as e:
        logger.error(f"Error running seeder: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='NutriLens Safe Database Seeder - Only adds new data')
    parser.add_argument('action', choices=[
        'seed', 'status', 'create-tables'
    ], help='Action to perform')
    
    args = parser.parse_args()
    
    db_manager = SafeDatabaseManager()
    
    if args.action == 'status':
        logger.info("Checking database status...")
        db_manager.check_data_status()
    
    elif args.action == 'create-tables':
        logger.info("Creating database tables if needed...")
        db_manager.create_tables_if_needed()
    
    elif args.action == 'seed':
        logger.info("Starting SAFE incremental database seeding...")
        logger.info("This will ONLY add new recipes and items - existing data is preserved")
        
        # Check current status
        status = db_manager.check_data_status()
        if status:
            logger.info("All existing data will be preserved.")
        
        # Ensure tables exist
        db_manager.create_tables_if_needed()
        
        # Run safe incremental seeder
        success = run_safe_seeder()
        if success:
            logger.info("✅ Safe seeding completed successfully!")
            logger.info("Checking final database status...")
            db_manager.check_data_status()
        else:
            logger.error("❌ Seeding failed!")

if __name__ == "__main__":
    main()

# Usage examples:
"""
# Check current database status
python seed_runner.py status

# Create database tables if needed
python seed_runner.py create-tables

# Add new recipes and items (100% SAFE - preserves existing data)
python seed_runner.py seed

This script ONLY adds new data and NEVER deletes anything.
Your existing recipes, food items, and relationships are completely safe.
"""