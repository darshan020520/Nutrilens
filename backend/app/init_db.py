import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from app.models.database import Base, engine
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    """Initialize database with all tables"""
    try:
        # Create all tables
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully!")
        
        # Create indexes
        logger.info("Creating indexes...")
        with engine.connect() as conn:
            # Add composite indexes for better performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);",
                "CREATE INDEX IF NOT EXISTS idx_meal_logs_user_date ON meal_logs(user_id, planned_datetime);",
                "CREATE INDEX IF NOT EXISTS idx_user_inventory_user_item ON user_inventory(user_id, item_id);",
                "CREATE INDEX IF NOT EXISTS idx_recipes_goals ON recipes USING GIN(goals);",
                "CREATE INDEX IF NOT EXISTS idx_recipes_dietary ON recipes USING GIN(dietary_tags);",
                "CREATE INDEX IF NOT EXISTS idx_agent_interactions_user_date ON agent_interactions(user_id, created_at DESC);"
            ]
            
            for index in indexes:
                try:
                    conn.execute(index)
                    logger.info(f"Index created: {index[:50]}...")
                except Exception as e:
                    logger.warning(f"Index might already exist: {e}")
        
        logger.info("Database initialization complete!")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

if __name__ == "__main__":
    init_database()