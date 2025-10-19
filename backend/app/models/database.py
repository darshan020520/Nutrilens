#/backend/models/database.py
from sqlalchemy import create_engine, Column, Integer, String, Float, JSON, DateTime, ForeignKey, Text, Boolean, Time, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import enum
from app.core.config import settings

# Add these enums
class NotificationProvider(str, enum.Enum):  # Changed from Enum to enum.Enum
    PUSH = "push"
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"

class NotificationStatus(str, enum.Enum):  # Changed from Enum to enum.Enum
    SENT = "sent"
    FAILED = "failed"
    PENDING = "pending"

Base = declarative_base()

# Create engine
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Enums
class GoalType(str, enum.Enum):
    MUSCLE_GAIN = "muscle_gain"
    FAT_LOSS = "fat_loss"
    BODY_RECOMP = "body_recomp"
    WEIGHT_TRAINING = "weight_training"
    ENDURANCE = "endurance"
    GENERAL_HEALTH = "general_health"

class PathType(str, enum.Enum):
    IF_16_8 = "if_16_8"
    IF_18_6 = "if_18_6"
    OMAD = "omad"
    TRADITIONAL = "traditional"
    BODYBUILDER = "bodybuilder"

class ActivityLevel(str, enum.Enum):
    SEDENTARY = "sedentary"
    LIGHTLY_ACTIVE = "lightly_active"
    MODERATELY_ACTIVE = "moderately_active"
    VERY_ACTIVE = "very_active"
    EXTRA_ACTIVE = "extra_active"

class DietaryType(str, enum.Enum):
    VEGETARIAN = "vegetarian"
    NON_VEGETARIAN = "non_vegetarian"
    VEGAN = "vegan"
    PESCATARIAN = "pescatarian"

# User Tables
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    onboarding_completed = Column(Boolean, default=False, nullable=False)
    onboarding_current_step = Column(Integer, default=1, nullable=False)
    basic_info_completed = Column(Boolean, default=False, nullable=False)
    goal_selection_completed = Column(Boolean, default=False, nullable=False)
    path_selection_completed = Column(Boolean, default=False, nullable=False)
    preferences_completed = Column(Boolean, default=False, nullable=False)
    onboarding_started_at = Column(DateTime, nullable=True)
    onboarding_completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    goal = relationship("UserGoal", back_populates="user", uselist=False, cascade="all, delete-orphan")
    path = relationship("UserPath", back_populates="user", uselist=False, cascade="all, delete-orphan")
    preferences = relationship("UserPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")
    pantry = relationship("UserInventory", back_populates="user", cascade="all, delete-orphan")
    meal_plans = relationship("MealPlan", back_populates="user", cascade="all, delete-orphan")
    meal_logs = relationship("MealLog", back_populates="user", cascade="all, delete-orphan")
    receipt_uploads = relationship("ReceiptUpload", back_populates="user", cascade="all, delete-orphan")
    receipt_scans = relationship("ReceiptScan", back_populates="user", cascade="all, delete-orphan")
    agent_interactions = relationship("AgentInteraction", back_populates="user", cascade="all, delete-orphan")
    whatsapp_logs = relationship("WhatsappLog", back_populates="user", cascade="all, delete-orphan")
    notification_preference = relationship("NotificationPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")
    notification_logs = relationship("NotificationLog", back_populates="user", cascade="all, delete-orphan")

class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    name = Column(String(255))
    age = Column(Integer)
    height_cm = Column(Float)
    weight_kg = Column(Float)
    sex = Column(String(10))  # male/female
    activity_level = Column(Enum(ActivityLevel))
    medical_conditions = Column(JSON, default=list)
    bmr = Column(Float, nullable=True)  # Calculated
    tdee = Column(Float, nullable=True)  # Calculated
    goal_calories = Column(Float, nullable=True)  # Calculated based on goal
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="profile")

class UserGoal(Base):
    __tablename__ = "user_goals"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    goal_type = Column(Enum(GoalType), nullable=False)
    target_weight = Column(Float, nullable=True)
    target_date = Column(DateTime, nullable=True)
    target_body_fat_percentage = Column(Float, nullable=True)
    macro_targets = Column(JSON)  # {"protein": 0.3, "carbs": 0.45, "fat": 0.25}
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    user = relationship("User", back_populates="goal")

class UserPath(Base):
    __tablename__ = "user_paths"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    path_type = Column(Enum(PathType), nullable=False)
    meals_per_day = Column(Integer)
    meal_windows = Column(JSON)  # [{"meal": "breakfast", "start": "08:00", "end": "09:00"}]
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="path")

class UserPreference(Base):
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    dietary_type = Column(Enum(DietaryType))
    allergies = Column(JSON, default=list)  # ["nuts", "dairy"]
    disliked_ingredients = Column(JSON, default=list)
    cuisine_preferences = Column(JSON, default=list)  # ["indian", "continental"]
    max_prep_time_weekday = Column(Integer, default=30)  # minutes
    max_prep_time_weekend = Column(Integer, default=60)  # minutes
    
    user = relationship("User", back_populates="preferences")

# Nutrition Tables
class Item(Base):
    __tablename__ = "items"
    
    id = Column(Integer, primary_key=True, index=True)
    canonical_name = Column(String(255), unique=True, index=True)
    aliases = Column(JSON, default=list)  # ["whole wheat flour", "atta", "ww flour"]
    category = Column(String(50))  # grains, protein, vegetables, etc.
    unit = Column(String(50), default="g")
    barcode = Column(String(100), nullable=True, index=True)
    fdc_id = Column(String(50), nullable=True)
    nutrition_per_100g = Column(JSON)  # {"calories": 340, "protein_g": 13.2, ...}
    is_staple = Column(Boolean, default=False)
    density_g_per_ml = Column(Float, nullable=True)
    
    # Relationships
    inventory_items = relationship("UserInventory", back_populates="item")
    recipe_ingredients = relationship("RecipeIngredient", back_populates="item")

class Recipe(Base):
    __tablename__ = "recipes"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True)
    description = Column(Text)
    goals = Column(JSON, default=list)  # ["muscle_gain", "fat_loss"]
    tags = Column(JSON, default=list)  # ["high_protein", "quick", "meal_prep_friendly"]
    dietary_tags = Column(JSON, default=list)  # ["vegetarian", "gluten_free"]
    suitable_meal_times = Column(JSON, default=list)  # ["breakfast", "lunch", "dinner"]
    instructions = Column(JSON, default=list)  # List of steps
    cuisine = Column(String(50))
    prep_time_min = Column(Integer)
    cook_time_min = Column(Integer)
    difficulty_level = Column(String(20))  # easy, medium, hard
    servings = Column(Integer, default=1)
    macros_per_serving = Column(JSON)  # {"calories": 450, "protein_g": 45, ...}
    meal_prep_notes = Column(Text, nullable=True)
    chef_tips = Column(Text, nullable=True)
    
    # Relationships
    ingredients = relationship("RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan")
    meal_logs = relationship("MealLog", back_populates="recipe")

class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    
    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    item_id = Column(Integer, ForeignKey("items.id"))
    quantity_grams = Column(Float)
    is_optional = Column(Boolean, default=False)
    preparation_notes = Column(String(255), nullable=True)  # "diced", "minced", etc.
    
    # Relationships
    recipe = relationship("Recipe", back_populates="ingredients")
    item = relationship("Item", back_populates="recipe_ingredients")

# Planning Tables
class MealPlan(Base):
    __tablename__ = "meal_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    week_start_date = Column(DateTime, index=True)
    plan_data = Column(JSON)  # Complete week structure
    grocery_list = Column(JSON)  # Aggregated shopping list
    total_calories = Column(Float)
    avg_macros = Column(JSON)  # Average daily macros
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    user = relationship("User", back_populates="meal_plans")

class MealLog(Base):
    __tablename__ = "meal_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=True)
    meal_type = Column(String(20))  # breakfast, lunch, dinner, snack
    planned_datetime = Column(DateTime, index=True)
    consumed_datetime = Column(DateTime, nullable=True)
    was_skipped = Column(Boolean, default=False)
    skip_reason = Column(String(255), nullable=True)
    portion_multiplier = Column(Float, default=1.0)
    notes = Column(Text, nullable=True)
    external_meal = Column(JSON, nullable=True)  # For eating out
    
    user = relationship("User", back_populates="meal_logs")
    recipe = relationship("Recipe", back_populates="meal_logs")

class UserInventory(Base):
    __tablename__ = "user_inventory"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    quantity_grams = Column(Float)
    purchase_date = Column(DateTime, default=datetime.utcnow)
    expiry_date = Column(DateTime, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    source = Column(String(20))  # manual, ocr, deduction
    
    user = relationship("User", back_populates="pantry")
    item = relationship("Item", back_populates="inventory_items")

# Tracking Tables
class ReceiptUpload(Base):
    __tablename__ = "receipt_uploads"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    file_url = Column(String(500))
    ocr_raw_text = Column(Text, nullable=True)
    parsed_items = Column(JSON, nullable=True)
    processing_status = Column(String(20))  # pending, processing, completed, failed
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="receipt_uploads")

class AgentInteraction(Base):
    __tablename__ = "agent_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    agent_type = Column(String(50))  # planning, tracking, nutrition, whatsapp
    interaction_type = Column(String(50))  # command, query, notification
    input_text = Column(Text, nullable=True)
    response_text = Column(Text, nullable=True)
    context_data = Column(JSON, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    user = relationship("User", back_populates="agent_interactions")

class WhatsappLog(Base):
    __tablename__ = "whatsapp_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    message_type = Column(String(20))  # incoming, outgoing
    command = Column(String(50), nullable=True)
    message = Column(Text)
    delivered = Column(Boolean, default=False)
    read = Column(Boolean, default=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="whatsapp_logs")


class NotificationPreference(Base):
    """User notification preferences"""
    __tablename__ = "notification_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True)
    
    # Provider preferences (which channels to use)
    enabled_providers = Column(JSON, default=lambda: ["push"])
    
    # Notification type preferences (what types to send)
    enabled_types = Column(JSON, default=lambda: [
        "meal_reminder", "inventory_alert", "achievement"
    ])
    
    # Timing preferences
    quiet_hours_start = Column(Integer, default=22)  # 10 PM
    quiet_hours_end = Column(Integer, default=7)     # 7 AM
    timezone = Column(String(50), default="UTC")
    
    # Contact information
    phone_number = Column(String(20), nullable=True)
    whatsapp_number = Column(String(20), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="notification_preference")

class NotificationLog(Base):
    """Log of notification attempts for debugging and analytics"""
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    # Notification details
    notification_type = Column(String(50), index=True)
    provider = Column(Enum(NotificationProvider), nullable=True)
    status = Column(Enum(NotificationStatus), index=True)

    # Content
    title = Column(String(255))
    body = Column(Text)
    data = Column(JSON, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="notification_logs")


# Receipt Scanner Integration Tables
class ReceiptScan(Base):
    """Track receipt scanning uploads and processing status"""
    __tablename__ = "receipt_scans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    s3_url = Column(Text, nullable=False)
    status = Column(String(20), default="processing")  # processing, completed, failed
    items_count = Column(Integer, nullable=True)
    auto_added_count = Column(Integer, nullable=True)
    needs_confirmation_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="receipt_scans")
    pending_items = relationship("ReceiptPendingItem", back_populates="receipt_scan", cascade="all, delete-orphan")


class ReceiptPendingItem(Base):
    """Store items needing user confirmation from receipt scans"""
    __tablename__ = "receipt_pending_items"

    id = Column(Integer, primary_key=True, index=True)
    receipt_scan_id = Column(Integer, ForeignKey("receipt_scans.id", ondelete="CASCADE"), nullable=False, index=True)
    item_name = Column(Text, nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)
    suggested_item_id = Column(Integer, ForeignKey("items.id"), nullable=True)
    confidence = Column(Float, nullable=True)
    status = Column(String(20), default="pending", index=True)  # pending, confirmed, skipped
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)

    # Relationships
    receipt_scan = relationship("ReceiptScan", back_populates="pending_items")
    suggested_item = relationship("Item")