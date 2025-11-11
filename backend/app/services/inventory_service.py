#/backend/services/inventory.py
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.database import UserInventory, Item, User, MealLog, Recipe, RecipeIngredient, UserProfile
# Legacy normalizer (kept for backward compatibility)
# from app.services.item_normalizer import IntelligentItemNormalizer, NormalizationResult

# NEW: RAG-based normalizer with vector embeddings
from app.services.item_normalizer_rag import RAGItemNormalizer, NormalizationResult
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class InventoryStatus:
    """Comprehensive inventory status for AI decision making"""
    total_items: int
    total_weight_g: float
    expiring_soon: List[Dict]  # Items expiring in next 3 days
    low_stock: List[Dict]  # Items below 20% of usual quantity
    categories_available: Dict[str, int]  # Count by category
    nutritional_capacity: Dict[str, float]  # Total protein, carbs, etc available
    estimated_days_remaining: int  # Based on consumption patterns
    recommendations: List[str]  # AI recommendations

class IntelligentInventoryService:
    """
    Smart inventory management that enables AI meal planning
    This service is the bridge between raw inventory and intelligent decisions
    """

    # Default shelf life by category (in days)
    CATEGORY_SHELF_LIFE = {
        'vegetables': 7,
        'fruits': 7,
        'dairy': 7,
        'meat': 5,
        'poultry': 5,
        'seafood': 3,
        'eggs': 21,
        'grains': 365,
        'legumes': 365,
        'nuts': 180,
        'oils': 180,
        'spices': 365,
        'condiments': 90,
        'beverages': 30,
        'default': 14  # 2 weeks for uncategorized items
    }

    def __init__(self, db: Session):
        self.db = db
        # Get all items for normalizer initialization
        items_list = self.db.query(Item).all()
        from app.core.config import settings

        # NEW: Initialize RAG normalizer with vector embeddings
        self.normalizer = RAGItemNormalizer(
            items_list=items_list,
            db=db,  # NEW: Pass db session for vector queries
            openai_api_key=settings.openai_api_key
        )

    def _get_default_expiry_days(self, item: Item) -> int:
        """Get default shelf life for item based on category"""
        category = item.category.lower() if item.category else 'default'
        return self.CATEGORY_SHELF_LIFE.get(category, self.CATEGORY_SHELF_LIFE['default'])

    def add_item(
        self,
        user_id: int,
        item_id: int,
        quantity_grams: float,
        expiry_date: Optional[datetime] = None,
        source: str = "manual"
    ) -> Dict:
        """
        Add item to inventory - PUBLIC METHOD
        Uses _add_to_inventory for consistent expiry date handling and batch management
        """
        try:
            # Get the item
            item = self.db.query(Item).filter(Item.id == item_id).first()
            if not item:
                return {"success": False, "error": "Item not found"}

            # Calculate expiry_days if expiry_date is provided
            expiry_days = None
            if expiry_date:
                expiry_days = (expiry_date - datetime.now()).days

            # Use _add_to_inventory which handles expiry dates and batch management
            self._add_to_inventory(
                user_id=user_id,
                item_id=item_id,
                quantity_grams=quantity_grams,
                expiry_days=expiry_days,
                source=source
            )

            self.db.commit()

            # Get total remaining quantity across all batches
            batches = self.db.query(UserInventory).filter(
                and_(
                    UserInventory.user_id == user_id,
                    UserInventory.item_id == item_id
                )
            ).all()
            total_remaining = sum(batch.quantity_grams for batch in batches)

            return {
                "success": True,
                "item": item.canonical_name,
                "quantity_added": quantity_grams,
                "remaining_quantity": total_remaining
            }

        except Exception as e:
            logger.error(f"Error adding item: {str(e)}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    def deduct_item(
        self,
        user_id: int,
        item_id: int,
        quantity_grams: float
    ) -> Dict:
        """
        Deduct item from inventory - PUBLIC METHOD for tracking agent
        """
        try:
            # Find item in inventory
            inventory_item = self.db.query(UserInventory).filter(
                and_(
                    UserInventory.user_id == user_id,
                    UserInventory.item_id == item_id
                )
            ).first()
            
            if not inventory_item:
                return {
                    "success": False,
                    "error": "Item not in inventory",
                    "remaining_quantity": 0
                }
            
            # Get item details
            item = self.db.query(Item).filter(Item.id == item_id).first()
            
            if inventory_item.quantity_grams < quantity_grams:
                # Not enough quantity
                deducted = inventory_item.quantity_grams
                inventory_item.quantity_grams = 0
                warning = f"Only {deducted}g available, deducted all"
            else:
                # Normal deduction
                inventory_item.quantity_grams -= quantity_grams
                deducted = quantity_grams
                warning = None
            
            inventory_item.last_updated = datetime.now()
            self.db.commit()
            
            result = {
                "success": True,
                "item": item.canonical_name if item else "Unknown",
                "quantity_deducted": deducted,
                "remaining_quantity": inventory_item.quantity_grams
            }
            
            if warning:
                result["warning"] = warning
            
            return result
            
        except Exception as e:
            logger.error(f"Error deducting item: {str(e)}")
            self.db.rollback()
            return {
                "success": False,
                "error": str(e),
                "remaining_quantity": 0
            }
        
    def add_items_from_text(self, user_id: int, text_input: str) -> Dict:
        """
        Process text input (like receipt) and add to inventory
        Returns detailed results for user confirmation
        """
        logger.info("🔷 INVENTORY SERVICE: add_items_from_text() called")
        logger.info(f"User ID: {user_id}")

        lines = text_input.strip().split('\n')
        logger.info(f"📝 Split into {len(lines)} lines")

        results = {
            'successful': [],
            'needs_confirmation': [],
            'failed': [],
            'summary': {}
        }

        for idx, line in enumerate(lines, 1):
            line = line.strip()
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing line {idx}/{len(lines)}: '{line}'")

            if not line:
                logger.info("⏭️  Skipping empty line")
                continue

            # Normalize the item
            logger.info(f"🔍 Calling normalizer.normalize('{line}')...")
            result = self.normalizer.normalize(line)

            print(f"\n{'='*80}")
            print(f"DEBUG: Processing '{line}'")
            print(f"  Confidence: {result.confidence}")
            print(f"  Alternatives type: {type(result.alternatives)}")
            print(f"  Alternatives value: {result.alternatives}")
            print(f"  Alternatives length: {len(result.alternatives) if result.alternatives else 'None/Empty'}")
            print(f"  bool(result.alternatives): {bool(result.alternatives)}")
            print(f"{'='*80}\n")

            logger.info(f"📊 Normalization result:")
            logger.info(f"   - Item: {result.item.canonical_name if result.item else 'None'}")
            logger.info(f"   - Confidence: {result.confidence:.3f}")
            logger.info(f"   - Matched on: {result.matched_on}")
            logger.info(f"   - Quantity: {result.extracted_quantity} {result.extracted_unit}")
            logger.info(f"   - Quantity in grams: {result.quantity_grams}")

            if result.confidence >= 0.85:
                # High confidence - auto add
                logger.info(f"✅ HIGH CONFIDENCE (≥0.85) - Auto-adding to inventory")
                inventory_item = self._add_to_inventory(
                    user_id,
                    result.item.id,
                    result.quantity_grams
                )
                logger.info(f"✅ Added: {result.item.canonical_name} ({inventory_item.quantity_grams}g)")

                results['successful'].append({
                    'original': line,
                    'matched': result.item.canonical_name,
                    'quantity': f"{inventory_item.quantity_grams}g",
                    'confidence': result.confidence
                })
            elif result.confidence >= 0.6:
                # Medium confidence - needs confirmation
                logger.info(f"⚠️  MEDIUM CONFIDENCE (0.6-0.84) - Needs confirmation")
                logger.info(f"   Alternatives: {[alt[0].canonical_name for alt in result.alternatives[:3]]}")

                results['needs_confirmation'].append({
                    'original': line,
                    'item_id': result.item.id if result.item else None,
                    'suggested': result.item.canonical_name if result.item else None,
                    'quantity': result.extracted_quantity,
                    'unit': result.extracted_unit,
                    'alternatives': [
                        {'item_id': alt[0].id, 'name': alt[0].canonical_name, 'confidence': alt[1]}
                        for alt in result.alternatives
                    ],
                    'confidence': result.confidence
                })
            elif result.confidence >= 0.40 and result.alternatives:
                # Low-medium confidence with suggestions - let user pick
                logger.info(f"⚠️  LOW-MEDIUM CONFIDENCE (0.4-0.59) - Has suggestions, needs user selection")
                logger.info(f"   Suggestions: {[alt[0].canonical_name for alt in result.alternatives[:5]]}")

                results['needs_confirmation'].append({
                    'original': line,
                    'quantity_grams': result.quantity_grams,
                    'suggestions': [
                        {'item_id': alt[0].id, 'name': alt[0].canonical_name, 'confidence': alt[1]}
                        for alt in result.alternatives[:5]
                    ]
                })
            else:
                # Very low confidence - failed
                logger.info(f"❌ VERY LOW CONFIDENCE (<0.4 or no suggestions) - Failed")

                results['failed'].append({
                    'original': line,
                    'reason': 'Could not identify item',
                    'suggestions': [
                        {'name': alt[0].canonical_name, 'confidence': alt[1]}
                        for alt in result.alternatives[:3]
                    ] if result.alternatives else []
                })

        # Generate summary
        results['summary'] = {
            'total_processed': len([l for l in lines if l.strip()]),
            'successful': len(results['successful']),
            'needs_confirmation': len(results['needs_confirmation']),
            'failed': len(results['failed']),
            'success_rate': len(results['successful']) / len([l for l in lines if l.strip()]) if lines else 0
        }

        logger.info(f"\n{'='*60}")
        logger.info("🔷 INVENTORY SERVICE: Complete")
        logger.info(f"Summary: {results['summary']}")

        return results
    
    def _add_to_inventory(self, user_id, item_id, quantity_grams, expiry_days=None):
        """
        Add item to inventory with smart batch management
        - Auto-assigns expiry based on category if not provided
        - Creates new batch if expiry differs by >2 days
        - Merges with existing batch if expiry is similar
        """
        logger.info(f"   📦 _add_to_inventory called: user_id={user_id}, item_id={item_id}, quantity_grams={quantity_grams}")

        # Get item to determine default expiry
        item = self.db.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise ValueError(f"Item {item_id} not found")

        # Calculate expiry date
        if expiry_days is None:
            expiry_days = self._get_default_expiry_days(item)
            logger.info(f"   📅 Auto-assigned expiry: {expiry_days} days (category: {item.category})")

        new_expiry_date = datetime.now() + timedelta(days=expiry_days)

        # Find existing batches for this item
        existing_batches = self.db.query(UserInventory).filter(
            and_(
                UserInventory.user_id == user_id,
                UserInventory.item_id == item_id
            )
        ).all()

        # Try to find a batch with similar expiry (within 2 days)
        matching_batch = None
        for batch in existing_batches:
            if batch.expiry_date:
                days_diff = abs((batch.expiry_date - new_expiry_date).days)
                if days_diff <= 2:  # Merge if expiry within 2 days
                    matching_batch = batch
                    break

        if matching_batch:
            logger.info(f"   ♻️  Merging with existing batch (expiry: {matching_batch.expiry_date.date()})")
            logger.info(f"   Current: {matching_batch.quantity_grams}g → New: {matching_batch.quantity_grams + quantity_grams}g")
            matching_batch.quantity_grams += quantity_grams
            matching_batch.last_updated = datetime.now()
            inventory_item = matching_batch
        else:
            logger.info(f"   ➕ Creating new batch (expiry: {new_expiry_date.date()})")
            inventory_item = UserInventory(
                user_id=user_id,
                item_id=item_id,
                quantity_grams=quantity_grams,
                purchase_date=datetime.now(),
                expiry_date=new_expiry_date,
                source='manual_add'
            )
            self.db.add(inventory_item)

        self.db.commit()
        logger.info(f"   ✅ Committed to database - Final quantity: {inventory_item.quantity_grams}g")
        return inventory_item
    
    def deduct_for_meal(
        self,
        user_id: int,
        recipe_id: int,
        portion_multiplier: float = 1.0
    ) -> Dict:
        """
        Intelligently deduct ingredients when a meal is consumed
        Returns what was deducted and any warnings
        """
        # Get recipe ingredients
        ingredients = self.db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == recipe_id
        ).all()
        
        deductions = []
        warnings = []
        
        for ingredient in ingredients:
            if ingredient.is_optional:
                continue
            
            required_amount = ingredient.quantity_grams * portion_multiplier
            
            # Find item in inventory
            inventory_item = self.db.query(UserInventory).filter(
                and_(
                    UserInventory.user_id == user_id,
                    UserInventory.item_id == ingredient.item_id
                )
            ).first()
            
            if not inventory_item:
                warnings.append(f"Item {ingredient.item.canonical_name} not in inventory")
                continue
            
            if inventory_item.quantity_grams < required_amount:
                warnings.append(
                    f"Not enough {ingredient.item.canonical_name}: "
                    f"needed {required_amount}g, have {inventory_item.quantity_grams}g"
                )
                # Deduct what's available
                deducted = inventory_item.quantity_grams
                inventory_item.quantity_grams = 0
            else:
                # Normal deduction
                inventory_item.quantity_grams -= required_amount
                deducted = required_amount
            
            inventory_item.last_updated = datetime.now()
            
            deductions.append({
                'item': ingredient.item.canonical_name,
                'deducted': deducted,
                'remaining': inventory_item.quantity_grams
            })
            
            # Check if item is now low
            if inventory_item.quantity_grams < 50:  # Less than 50g
                warnings.append(f"{ingredient.item.canonical_name} is running low")
        
        self.db.commit()
        
        return {
            'deductions': deductions,
            'warnings': warnings,
            'success': len(warnings) == 0
        }
    
    def get_inventory_status(self, user_id: int) -> InventoryStatus:
        """
        Get comprehensive inventory status for AI decision making
        This is what the AI agents will use to make intelligent decisions

        OPTIMIZED: Uses eager loading to eliminate N+1 query problem
        """
        from sqlalchemy.orm import joinedload

        # OPTIMIZATION: Load inventory WITH related items in ONE query
        inventory = self.db.query(UserInventory).options(
            joinedload(UserInventory.item)
        ).filter(
            UserInventory.user_id == user_id
        ).all()
        
        if not inventory:
            return InventoryStatus(
                total_items=0,
                total_weight_g=0,
                expiring_soon=[],
                low_stock=[],
                categories_available={},
                nutritional_capacity={},
                estimated_days_remaining=0,
                recommendations=["Your inventory is empty. Add items to get started!"]
            )
        
        # Calculate totals
        total_items = len(inventory)
        total_weight = sum(item.quantity_grams for item in inventory)

        # OPTIMIZATION: Single loop processes all data (was 3 separate loops)
        expiring_soon = []
        low_stock = []
        categories = {}
        nutritional_capacity = {
            'calories': 0,
            'protein_g': 0,
            'carbs_g': 0,
            'fat_g': 0
        }

        three_days_later = datetime.now() + timedelta(days=3)

        for inv_item in inventory:
            # Item already loaded via joinedload - NO additional query!
            item = inv_item.item

            if not item:
                continue

            # Find expiring items
            if inv_item.expiry_date and inv_item.expiry_date <= three_days_later:
                expiring_soon.append({
                    'item': item.canonical_name,
                    'quantity': inv_item.quantity_grams,
                    'expires_in_days': (inv_item.expiry_date - datetime.now()).days
                })

            # Find low stock items
            if inv_item.quantity_grams < 100:
                low_stock.append({
                    'item': item.canonical_name,
                    'quantity': inv_item.quantity_grams
                })

            # Category analysis
            category = item.category or 'uncategorized'
            categories[category] = categories.get(category, 0) + 1

            # Nutritional capacity
            if item.nutrition_per_100g:
                factor = inv_item.quantity_grams / 100
                for nutrient in nutritional_capacity:
                    if nutrient in item.nutrition_per_100g:
                        nutritional_capacity[nutrient] += item.nutrition_per_100g[nutrient] * factor

        # Estimate days remaining based on user's calorie needs
        user_profile = self.db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if user_profile and user_profile.goal_calories:
            days_remaining = int(nutritional_capacity['calories'] / user_profile.goal_calories) if user_profile.goal_calories > 0 else 0
        else:
            days_remaining = int(nutritional_capacity['calories'] / 2000) if nutritional_capacity['calories'] > 0 else 0

        # Generate AI recommendations
        recommendations = self._generate_recommendations(
            inventory,
            expiring_soon,
            categories,
            nutritional_capacity,
            days_remaining
        )
        
        return InventoryStatus(
            total_items=total_items,
            total_weight_g=total_weight,
            expiring_soon=expiring_soon,
            low_stock=low_stock,
            categories_available=categories,
            nutritional_capacity=nutritional_capacity,
            estimated_days_remaining=days_remaining,
            recommendations=recommendations
        )
    
    def get_user_inventory(self, user_id: int, category: str = None, low_stock_only: bool = False, expiring_soon: bool = False):
        """Fetch inventory items for a specific user with optional filters."""
        query = self.db.query(UserInventory).filter(UserInventory.user_id == user_id)

        if low_stock_only:
            query = query.filter(UserInventory.quantity_grams < 100)

        if expiring_soon:
            three_days_later = datetime.now() + timedelta(days=3)
            query = query.filter(UserInventory.expiry_date <= three_days_later)

        inventory_items = query.all()

        items = []
        for inv in inventory_items:
            item = self.db.query(Item).filter(Item.id == inv.item_id).first()
            if category and item.category != category:
                continue

            days_until_expiry = None
            if inv.expiry_date:
                days_until_expiry = (inv.expiry_date - datetime.now()).days

            items.append({
                "id": inv.id,
                "item_id": item.id,
                "item_name": item.canonical_name,
                "category": item.category,
                "quantity_grams": inv.quantity_grams,
                "expiry_date": inv.expiry_date.isoformat() if inv.expiry_date else None,
                "days_until_expiry": days_until_expiry
            })

        return {"count": len(items), "items": items}
    
    def _generate_recommendations(
        self,
        inventory: List[UserInventory],
        expiring_soon: List[Dict],
        categories: Dict,
        nutritional_capacity: Dict,
        days_remaining: int
    ) -> List[str]:
        """
        Generate intelligent recommendations based on inventory analysis
        This is where AI shines - providing actionable insights
        """
        recommendations = []
        
        # Expiry warnings
        if expiring_soon:
            items_str = ', '.join([item['item'] for item in expiring_soon[:3]])
            recommendations.append(f"🚨 Use soon: {items_str}")
        
        # Low diversity warning
        if len(categories) < 3:
            recommendations.append("📦 Add more variety - you're missing key food groups")
        
        # Protein check
        if nutritional_capacity['protein_g'] < 200:
            recommendations.append("💪 Low protein stock - consider adding chicken, paneer, or lentils")
        
        # Days remaining
        if days_remaining < 3:
            recommendations.append(f"🛒 Only {days_remaining} days of food remaining - time to shop!")
        elif days_remaining > 14:
            recommendations.append("✅ Well stocked! You have plenty of food")
        
        # Category-specific
        if 'vegetables' not in categories or categories.get('vegetables', 0) < 3:
            recommendations.append("🥬 Add more vegetables for balanced nutrition")
        
        if 'protein' not in categories:
            recommendations.append("🥩 No protein sources found - essential for your goals")
        
        return recommendations if recommendations else ["✅ Inventory looks good!"]
    
    def check_recipe_availability(self, user_id: int, recipe_id: int) -> Dict:
        """
        Check if user has ingredients for a recipe
        Returns detailed availability report for AI planning
        """
        recipe = self.db.query(Recipe).filter(Recipe.id == recipe_id).first()
        if not recipe:
            return {'available': False, 'reason': 'Recipe not found'}
        
        ingredients = self.db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == recipe_id
        ).all()
        
        availability = {
            'recipe': recipe.title,
            'can_make': True,
            'missing_items': [],
            'insufficient_items': [],
            'available_items': [],
            'coverage_percentage': 0
        }
        
        total_ingredients = 0
        available_count = 0
        
        for ingredient in ingredients:
            if ingredient.is_optional:
                continue
            
            total_ingredients += 1
            
            # Check inventory
            inventory_item = self.db.query(UserInventory).filter(
                and_(
                    UserInventory.user_id == user_id,
                    UserInventory.item_id == ingredient.item_id
                )
            ).first()
            
            item = self.db.query(Item).filter(Item.id == ingredient.item_id).first()
            
            if not inventory_item:
                availability['missing_items'].append({
                    'item': item.canonical_name,
                    'required': ingredient.quantity_grams
                })
                availability['can_make'] = False
            elif inventory_item.quantity_grams < ingredient.quantity_grams:
                availability['insufficient_items'].append({
                    'item': item.canonical_name,
                    'required': ingredient.quantity_grams,
                    'available': inventory_item.quantity_grams,
                    'shortage': ingredient.quantity_grams - inventory_item.quantity_grams
                })
                availability['can_make'] = False
            else:
                availability['available_items'].append({
                    'item': item.canonical_name,
                    'required': ingredient.quantity_grams,
                    'available': inventory_item.quantity_grams
                })
                available_count += 1
        
        availability['coverage_percentage'] = (available_count / total_ingredients * 100) if total_ingredients > 0 else 0
        
        return availability
    
    def get_makeable_recipes(
        self,
        user_id: int,
        limit: int = 10,
        partial_threshold: float = 80.0
    ) -> Dict[str, List[Dict]]:
        """
        Find recipes user can make with current inventory

        Uses optimized SQL pre-filtering to avoid checking all recipes.
        Returns categorized results: fully_makeable (100%) and partially_makeable (>=80%)

        Args:
            user_id: User ID
            limit: Maximum recipes per category
            partial_threshold: Minimum match percentage for partial matches (default: 80%)

        Returns:
            {
                'fully_makeable': [recipe_data, ...],
                'partially_makeable': [recipe_data, ...]
            }
        """
        from sqlalchemy import func, case, Float

        # Step 1: Get user inventory
        user_inventory = self.db.query(
            UserInventory.item_id,
            UserInventory.quantity_grams
        ).filter(
            UserInventory.user_id == user_id,
            UserInventory.quantity_grams > 0
        ).all()

        if not user_inventory:
            return {'fully_makeable': [], 'partially_makeable': []}

        user_items = {item_id: qty for item_id, qty in user_inventory}
        user_item_ids = set(user_items.keys())

        # Step 2: SQL pre-filtering - only fetch recipes with >= threshold match
        # This avoids checking all recipes one by one
        recipe_match_subquery = self.db.query(
            Recipe.id.label('recipe_id'),
            func.count(RecipeIngredient.id).label('total_ingredients'),
            func.sum(
                case((RecipeIngredient.item_id.in_(user_item_ids), 1), else_=0)
            ).label('matching_ingredients'),
            (func.sum(
                case((RecipeIngredient.item_id.in_(user_item_ids), 1), else_=0)
            ).cast(Float) * 100.0 / func.count(RecipeIngredient.id)).label('estimated_match_pct')
        ).join(
            RecipeIngredient, Recipe.id == RecipeIngredient.recipe_id
        ).filter(
            RecipeIngredient.is_optional == False
        ).group_by(
            Recipe.id
        ).having(
            func.count(RecipeIngredient.id) > 0  # Recipe must have ingredients
        ).subquery()

        # Fetch promising recipes (3x limit as buffer for quantity validation)
        recipe_candidates = self.db.query(
            Recipe,
            recipe_match_subquery.c.total_ingredients,
            recipe_match_subquery.c.matching_ingredients,
            recipe_match_subquery.c.estimated_match_pct
        ).join(
            recipe_match_subquery,
            Recipe.id == recipe_match_subquery.c.recipe_id
        ).filter(
            recipe_match_subquery.c.estimated_match_pct >= partial_threshold
        ).order_by(
            recipe_match_subquery.c.estimated_match_pct.desc(),
            Recipe.prep_time_min.asc()
        ).limit(limit * 3).all()

        # Step 3: Validate quantities for promising recipes only
        fully_makeable = []
        partially_makeable = []

        for recipe, total_ing, matching_ing, estimated_pct in recipe_candidates:
            # Get detailed availability (validates actual quantities)
            availability = self.check_recipe_availability(user_id, recipe.id)

            # Extract ingredient names
            available_names = [item['item'] for item in availability['available_items']]
            missing_names = [item['item'] for item in availability['missing_items']]
            missing_names.extend([item['item'] for item in availability['insufficient_items']])

            total_ingredients = len(available_names) + len(missing_names)
            actual_match_pct = availability['coverage_percentage']

            # Skip if quantity check reveals it's below threshold
            if actual_match_pct < partial_threshold:
                continue

            # Build complete recipe data with all required fields
            recipe_data = {
                'recipe_id': recipe.id,
                'recipe_name': recipe.title,
                'description': recipe.description,
                'prep_time_minutes': recipe.prep_time_min,
                'servings': recipe.servings,
                'available_ingredients': len(available_names),
                'total_ingredients': total_ingredients,
                'available_ingredient_names': available_names,
                'match_percentage': round(actual_match_pct, 1),
                'macros': recipe.macros_per_serving,
                'goals': recipe.goals
            }

            if availability['can_make']:
                # 100% match - fully makeable
                fully_makeable.append(recipe_data)
            else:
                # Partial match (80-99%)
                recipe_data['missing_ingredient_names'] = missing_names
                partially_makeable.append(recipe_data)

            # Early exit if we have enough in both categories
            if len(fully_makeable) >= limit and len(partially_makeable) >= limit:
                break

        # Final sorting
        fully_makeable.sort(key=lambda x: x.get('prep_time_minutes', 999))
        partially_makeable.sort(
            key=lambda x: (-x.get('match_percentage', 0), x.get('prep_time_minutes', 999))
        )

        return {
            'fully_makeable': fully_makeable[:limit],
            'partially_makeable': partially_makeable[:limit]
        }

    async def process_receipt_items(
        self,
        user_id: int,
        receipt_items: List[Dict],
        auto_add_threshold: float = 0.75
    ) -> Dict:
        """
        Process receipt items with LLM-enhanced normalizer
        This is the main method for receipt scanner integration

        Args:
            user_id: User ID
            receipt_items: Raw items from receipt scanner
                Example: [{"item_name": "Onion", "quantity": 2, "unit": "kg"}]
            auto_add_threshold: Confidence threshold for auto-adding (default: 0.75)

        Returns:
            {
                "auto_added": List of auto-added items,
                "needs_confirmation": List of items needing review
            }
        """
        try:
            # Use LLM-enhanced normalizer's batch processing
            normalized_results = await self.normalizer.normalize_batch(receipt_items)

            # Categorize by confidence
            auto_added = []
            needs_confirmation = []

            for result in normalized_results:
                result_dict = result.to_dict()

                if result.confidence >= auto_add_threshold and result.item and result.quantity_grams:
                    # Auto-add to inventory (expiry auto-assigned by category)
                    inventory_item = self._add_to_inventory(
                        user_id=user_id,
                        item_id=result.item.id,
                        quantity_grams=result.quantity_grams,
                        expiry_days=None  # None = auto-assign based on category
                    )
                    auto_added.append(result_dict)
                    logger.info(f"Auto-added: {result.item.canonical_name} ({result.quantity_grams}g)")
                else:
                    # Needs confirmation
                    needs_confirmation.append(result_dict)
                    logger.info(f"Needs confirmation: {result.original_input} (confidence: {result.confidence})")

            return {
                "auto_added": auto_added,
                "needs_confirmation": needs_confirmation
            }

        except Exception as e:
            logger.error(f"Error processing receipt items: {str(e)}")
            raise