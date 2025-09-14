import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import get_db
from app.services.data_seeder import DataSeeder
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Seed the database with food items and recipes"""
    logger.info("Starting database seeding...")
    
    db = next(get_db())
    seeder = DataSeeder(db)
    
    try:
        seeder.seed_all()
        logger.info("✅ Database seeding completed successfully!")
    except Exception as e:
        logger.error(f"❌ Error during seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()