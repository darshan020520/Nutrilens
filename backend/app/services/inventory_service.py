from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.database import UserInventory, Item, User, MealLog, Recipe, RecipeIngredient, UserProfile
from app.services.item_normalizer import IntelligentItemNormalizer, NormalizationResult
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
    
    def __init__(self, db: Session):
        self.db = db
        self.normalizer = IntelligentItemNormalizer(db)
        
    def add_items_from_text(self, user_id: int, text_input: str) -> Dict:
        """
        Process text input (like receipt) and add to inventory
        Returns detailed results for user confirmation
        """
        lines = text_input.strip().split('\n')
        results = {
            'successful': [],
            'needs_confirmation': [],
            'failed': [],
            'summary': {}
        }
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Normalize the item
            result = self.normalizer.normalize(line)
            
            if result.confidence >= 0.85:
                # High confidence - auto add
                inventory_item = self._add_to_inventory(
                    user_id,
                    result.item,
                    result.extracted_quantity,
                    result.extracted_unit
                )
                results['successful'].append({
                    'original': line,
                    'matched': result.item.canonical_name,
                    'quantity': f"{inventory_item.quantity_grams}g",
                    'confidence': result.confidence
                })
            elif result.confidence >= 0.6:
                # Medium confidence - needs confirmation
                results['needs_confirmation'].append({
                    'original': line,
                    'suggested': result.item.canonical_name if result.item else None,
                    'alternatives': [
                        {'name': alt[0].canonical_name, 'confidence': alt[1]}
                        for alt in result.alternatives
                    ],
                    'confidence': result.confidence
                })
            else:
                # Low confidence - failed
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
            'total_processed': len(lines),
            'successful': len(results['successful']),
            'needs_confirmation': len(results['needs_confirmation']),
            'failed': len(results['failed']),
            'success_rate': len(results['successful']) / len(lines) if lines else 0
        }
        
        return results
    
    def _add_to_inventory(
        self,
        user_id: int,
        item: Item,
        quantity: float,
        unit: str,
        expiry_days: Optional[int] = None
    ) -> UserInventory:
        """Add or update item in user's inventory"""
        # Convert to grams
        quantity_grams = self.normalizer.convert_to_grams(quantity, unit, item)
        
        # Check if item already exists in inventory
        existing = self.db.query(UserInventory).filter(
            and_(
                UserInventory.user_id == user_id,
                UserInventory.item_id == item.id
            )
        ).first()
        
        if existing:
            # Update quantity
            existing.quantity_grams += quantity_grams
            existing.last_updated = datetime.now()
            inventory_item = existing
        else:
            # Create new inventory entry
            inventory_item = UserInventory(
                user_id=user_id,
                item_id=item.id,
                quantity_grams=quantity_grams,
                purchase_date=datetime.now(),
                expiry_date=datetime.now() + timedelta(days=expiry_days) if expiry_days else None,
                source='manual'
            )
            self.db.add(inventory_item)
        
        self.db.commit()
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
        """
        inventory = self.db.query(UserInventory).filter(
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
        
        # Find expiring items
        expiring_soon = []
        three_days_later = datetime.now() + timedelta(days=3)
        for inv_item in inventory:
            if inv_item.expiry_date and inv_item.expiry_date <= three_days_later:
                item = self.db.query(Item).filter(Item.id == inv_item.item_id).first()
                expiring_soon.append({
                    'item': item.canonical_name,
                    'quantity': inv_item.quantity_grams,
                    'expires_in_days': (inv_item.expiry_date - datetime.now()).days
                })
        
        # Analyze categories
        categories = {}
        nutritional_capacity = {
            'calories': 0,
            'protein_g': 0,
            'carbs_g': 0,
            'fat_g': 0
        }
        
        for inv_item in inventory:
            item = self.db.query(Item).filter(Item.id == inv_item.item_id).first()
            
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
            days_remaining = int(nutritional_capacity['calories'] / user_profile.goal_calories)
        else:
            days_remaining = int(nutritional_capacity['calories'] / 2000)  # Default 2000 cal/day
        
        # Generate AI recommendations
        recommendations = self._generate_recommendations(
            inventory,
            expiring_soon,
            categories,
            nutritional_capacity,
            days_remaining
        )
        
        # Find low stock items (simplified for now)
        low_stock = []
        for inv_item in inventory:
            if inv_item.quantity_grams < 100:  # Less than 100g
                item = self.db.query(Item).filter(Item.id == inv_item.item_id).first()
                low_stock.append({
                    'item': item.canonical_name,
                    'quantity': inv_item.quantity_grams
                })
        
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
    
    def get_makeable_recipes(self, user_id: int, limit: int = 10) -> List[Dict]:
        """
        Find all recipes the user can make with current inventory
        This is crucial for AI meal planning
        """
        # Get all recipes
        all_recipes = self.db.query(Recipe).all()
        makeable = []
        
        for recipe in all_recipes:
            availability = self.check_recipe_availability(user_id, recipe.id)
            
            if availability['can_make']:
                makeable.append({
                    'recipe_id': recipe.id,
                    'title': recipe.title,
                    'prep_time': recipe.prep_time_min,
                    'goals': recipe.goals,
                    'macros': recipe.macros_per_serving
                })
            elif availability['coverage_percentage'] >= 80:
                # Nearly makeable - include with note
                makeable.append({
                    'recipe_id': recipe.id,
                    'title': recipe.title,
                    'prep_time': recipe.prep_time_min,
                    'goals': recipe.goals,
                    'macros': recipe.macros_per_serving,
                    'note': f"Missing: {', '.join([m['item'] for m in availability['missing_items'][:2]])}"
                })
        
        # Sort by goal alignment (this would be enhanced with user preferences)
        makeable.sort(key=lambda x: x.get('prep_time', 999))
        
        return makeable[:limit]