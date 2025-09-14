import re
from typing import List, Tuple, Optional, Dict
from difflib import SequenceMatcher
from dataclasses import dataclass
import numpy as np
from sqlalchemy.orm import Session
from app.models.database import Item
import logging

logger = logging.getLogger(__name__)

@dataclass
class NormalizationResult:
    """Result of item normalization with confidence"""
    item: Optional[Item]
    confidence: float
    matched_on: str  # 'exact', 'alias', 'fuzzy', 'partial'
    alternatives: List[Tuple[Item, float]]  # Other possible matches
    original_input: str
    cleaned_input: str
    extracted_quantity: float
    extracted_unit: str

class IntelligentItemNormalizer:
    """
    AI-powered item normalizer that learns from patterns
    This is where we teach the system to understand human input
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.items_cache = self._build_cache()
        self.brand_patterns = self._load_brand_patterns()
        self.unit_patterns = self._compile_unit_patterns()
        self.common_misspellings = self._load_common_misspellings()
        
    def _build_cache(self) -> Dict:
        """Build intelligent cache with multiple access patterns"""
        items = self.db.query(Item).all()
        cache = {
            'by_name': {},
            'by_alias': {},
            'by_category': {},
            'by_tokens': {}
        }
        
        for item in items:
            # Direct name mapping
            cache['by_name'][item.canonical_name.lower()] = item
            
            # Alias mapping
            for alias in (item.aliases or []):
                cache['by_alias'][alias.lower()] = item
            
            # Category grouping for context
            category = item.category or 'uncategorized'
            if category not in cache['by_category']:
                cache['by_category'][category] = []
            cache['by_category'][category].append(item)
            
            # Token-based indexing for partial matches
            tokens = item.canonical_name.lower().split('_')
            for token in tokens:
                if token not in cache['by_tokens']:
                    cache['by_tokens'][token] = []
                cache['by_tokens'][token].append(item)
        
        logger.info(f"Built cache with {len(items)} items")
        return cache
    
    def _load_brand_patterns(self) -> List[re.Pattern]:
        """Patterns to identify and remove brand names"""
        brands = [
            r'\b(amul|britannia|maggi|nestle|kellogs|fortune|mdh|everest|patanjali|haldiram)\b',
            r'\b(tata|reliance|fresh|organic|premium|best|quality|supreme)\b',
            r'\b(brand|tm|®|©)\b'
        ]
        return [re.compile(pattern, re.IGNORECASE) for pattern in brands]
    
    def _compile_unit_patterns(self) -> Dict[str, re.Pattern]:
        """Compile patterns for extracting quantities and units"""
        return {
            'quantity_unit': re.compile(
                r'(\d+\.?\d*)\s*(kg|g|mg|l|ml|litre|liter|cup|tbsp|tsp|piece|pcs|packet|pack|bunch|dozen)',
                re.IGNORECASE
            ),
            'quantity_only': re.compile(r'^(\d+\.?\d*)\s+'),
            'unit_only': re.compile(r'\b(kg|g|mg|l|ml|litre|liter|cup|tbsp|tsp|piece|pcs)\b', re.IGNORECASE)
        }
    
    def _load_common_misspellings(self) -> Dict[str, str]:
        """Common misspellings and their corrections"""
        return {
            'chiken': 'chicken',
            'chikcen': 'chicken',
            'panner': 'paneer',
            'panir': 'paneer',
            'tamato': 'tomato',
            'tomoto': 'tomato',
            'onian': 'onion',
            'onoin': 'onion',
            'brocoli': 'broccoli',
            'broccolli': 'broccoli',
            'quinoa': 'quinoa',
            'kinwa': 'quinoa',
            'spinnach': 'spinach',
            'spinich': 'spinach',
            'yoghurt': 'yogurt',
            'curd': 'yogurt',
            'dhania': 'coriander',
            'pudina': 'mint',
            'atta': 'whole_wheat_flour',
            'maida': 'all_purpose_flour',
            'besan': 'chickpea_flour',
            'chawal': 'rice',
            'dal': 'lentils',
            'sabzi': 'vegetables',
            'mirch': 'chili',
            'adrak': 'ginger',
            'lahsun': 'garlic',
            'haldi': 'turmeric',
            'jeera': 'cumin',
            'dhania': 'coriander',
            'garam masala': 'garam_masala',
            'dhaniya': 'coriander',
            'shimla mirch': 'bell_pepper',
            'capsicum': 'bell_pepper'
        }
    
    def normalize(self, raw_input: str) -> NormalizationResult:
        """
        Main normalization function with AI-like intelligence
        Returns detailed result with confidence scoring
        """
        logger.debug(f"Normalizing: {raw_input}")
        
        # Step 1: Extract quantity and clean input
        quantity, unit, cleaned = self._extract_quantity_and_clean(raw_input)
        
        # Step 2: Try exact match first (100% confidence)
        if cleaned in self.items_cache['by_name']:
            return NormalizationResult(
                item=self.items_cache['by_name'][cleaned],
                confidence=1.0,
                matched_on='exact',
                alternatives=[],
                original_input=raw_input,
                cleaned_input=cleaned,
                extracted_quantity=quantity,
                extracted_unit=unit
            )
        
        # Step 3: Check aliases (95% confidence)
        if cleaned in self.items_cache['by_alias']:
            return NormalizationResult(
                item=self.items_cache['by_alias'][cleaned],
                confidence=0.95,
                matched_on='alias',
                alternatives=[],
                original_input=raw_input,
                cleaned_input=cleaned,
                extracted_quantity=quantity,
                extracted_unit=unit
            )
        
        # Step 4: Check common misspellings (90% confidence)
        corrected = self._correct_spelling(cleaned)
        if corrected != cleaned:
            if corrected in self.items_cache['by_name']:
                return NormalizationResult(
                    item=self.items_cache['by_name'][corrected],
                    confidence=0.9,
                    matched_on='spelling_correction',
                    alternatives=[],
                    original_input=raw_input,
                    cleaned_input=cleaned,
                    extracted_quantity=quantity,
                    extracted_unit=unit
                )
        
        # Step 5: Fuzzy matching with context awareness
        best_matches = self._fuzzy_match_with_context(cleaned)
        
        if best_matches:
            best_item, best_score = best_matches[0]
            alternatives = best_matches[1:4]  # Top 3 alternatives
            
            return NormalizationResult(
                item=best_item if best_score > 0.6 else None,
                confidence=best_score,
                matched_on='fuzzy',
                alternatives=alternatives,
                original_input=raw_input,
                cleaned_input=cleaned,
                extracted_quantity=quantity,
                extracted_unit=unit
            )
        
        # Step 6: Token-based partial matching
        partial_matches = self._token_based_matching(cleaned)
        if partial_matches:
            best_item, best_score = partial_matches[0]
            
            return NormalizationResult(
                item=best_item if best_score > 0.5 else None,
                confidence=best_score,
                matched_on='partial',
                alternatives=partial_matches[1:3],
                original_input=raw_input,
                cleaned_input=cleaned,
                extracted_quantity=quantity,
                extracted_unit=unit
            )
        
        # No match found
        return NormalizationResult(
            item=None,
            confidence=0.0,
            matched_on='none',
            alternatives=[],
            original_input=raw_input,
            cleaned_input=cleaned,
            extracted_quantity=quantity,
            extracted_unit=unit
        )
    
    def _extract_quantity_and_clean(self, text: str) -> Tuple[float, str, str]:
        """Extract quantity, unit and clean the text"""
        text = text.strip().lower()
        quantity = 1.0
        unit = 'unit'
        
        # Try to extract quantity and unit
        match = self.unit_patterns['quantity_unit'].search(text)
        if match:
            quantity = float(match.group(1))
            unit = match.group(2).lower()
            # Remove the matched part from text
            text = self.unit_patterns['quantity_unit'].sub('', text).strip()
        else:
            # Try just quantity
            match = self.unit_patterns['quantity_only'].search(text)
            if match:
                quantity = float(match.group(1))
                text = self.unit_patterns['quantity_only'].sub('', text).strip()
        
        # Remove brand names
        for brand_pattern in self.brand_patterns:
            text = brand_pattern.sub('', text).strip()
        
        # Clean up extra spaces and special characters
        text = re.sub(r'[^\w\s]', ' ', text)
        text = ' '.join(text.split())
        
        # Replace spaces with underscores for canonical matching
        text_underscore = text.replace(' ', '_')
        
        return quantity, unit, text_underscore
    
    def _correct_spelling(self, text: str) -> str:
        """Correct common misspellings"""
        # Direct correction
        if text in self.common_misspellings:
            return self.common_misspellings[text]
        
        # Check each word
        words = text.split('_')
        corrected_words = []
        for word in words:
            if word in self.common_misspellings:
                corrected_words.append(self.common_misspellings[word])
            else:
                corrected_words.append(word)
        
        return '_'.join(corrected_words)
    
    def _fuzzy_match_with_context(self, text: str) -> List[Tuple[Item, float]]:
        """
        Fuzzy matching with context awareness
        Returns list of (item, confidence) tuples sorted by confidence
        """
        matches = []
        
        for item_name, item in self.items_cache['by_name'].items():
            # Calculate base similarity
            similarity = SequenceMatcher(None, text, item_name).ratio()
            
            # Boost score if category context matches
            if any(cat_word in text for cat_word in str(item.category).split('_')):
                similarity += 0.1
            
            # Check aliases too
            for alias in (item.aliases or []):
                alias_similarity = SequenceMatcher(None, text, alias.lower()).ratio()
                similarity = max(similarity, alias_similarity)
            
            if similarity > 0.6:
                matches.append((item, min(similarity, 0.99)))  # Cap at 99%
        
        # Sort by confidence
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches
    
    def _token_based_matching(self, text: str) -> List[Tuple[Item, float]]:
        """Match based on individual tokens/words"""
        text_tokens = set(text.split('_'))
        matches = []
        
        for token in text_tokens:
            if token in self.items_cache['by_tokens']:
                for item in self.items_cache['by_tokens'][token]:
                    item_tokens = set(item.canonical_name.lower().split('_'))
                    # Calculate Jaccard similarity
                    intersection = len(text_tokens & item_tokens)
                    union = len(text_tokens | item_tokens)
                    similarity = intersection / union if union > 0 else 0
                    
                    if similarity > 0.3:
                        matches.append((item, similarity))
        
        # Remove duplicates and sort
        unique_matches = {}
        for item, score in matches:
            if item.id not in unique_matches or unique_matches[item.id][1] < score:
                unique_matches[item.id] = (item, score)
        
        matches = list(unique_matches.values())
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches
    
    def convert_to_grams(self, quantity: float, unit: str, item: Item) -> float:
        """
        Intelligent unit conversion with context awareness
        """
        # Standard conversions
        conversions = {
            'kg': 1000,
            'g': 1,
            'mg': 0.001,
            'l': 1000,  # Default water density
            'litre': 1000,
            'liter': 1000,
            'ml': 1,
            'cup': 240,
            'tbsp': 15,
            'tsp': 5,
            'piece': 100,  # Default estimate
            'pcs': 100,
            'packet': 200,  # Default estimate
            'pack': 200,
            'bunch': 150,  # For vegetables
            'dozen': 12  # Multiply by piece weight
        }
        
        # Get base conversion
        if unit in conversions:
            base_grams = quantity * conversions[unit]
            
            # Adjust for specific items
            if unit in ['piece', 'pcs']:
                # Item-specific piece weights
                piece_weights = {
                    'eggs': 50,
                    'banana': 120,
                    'apple': 180,
                    'onion': 150,
                    'tomato': 100,
                    'potato': 150,
                    'carrot': 60,
                    'bell_pepper': 120,
                    'chicken_breast': 200
                }
                
                if item and item.canonical_name in piece_weights:
                    base_grams = quantity * piece_weights[item.canonical_name]
            
            # Adjust for liquids with density
            if unit in ['l', 'ml', 'litre', 'liter'] and item and item.density_g_per_ml:
                base_grams *= item.density_g_per_ml
            
            return base_grams
        
        # Default to quantity * 100g if unit unknown
        return quantity * 100
    
    def learn_from_confirmation(self, original_input: str, confirmed_item: Item, was_correct: bool):
        """
        Learn from user confirmations to improve future matching
        This is where the AI aspect comes in - learning from feedback
        """
        if was_correct:
            # Add to aliases if not already there
            cleaned = self._extract_quantity_and_clean(original_input)[2]
            if cleaned not in self.items_cache['by_alias']:
                # In a production system, this would update the database
                logger.info(f"Learning: '{cleaned}' maps to '{confirmed_item.canonical_name}'")
                self.items_cache['by_alias'][cleaned] = confirmed_item
        else:
            # Log for analysis - in production, this would feed back to training
            logger.info(f"Incorrect match: '{original_input}' was not '{confirmed_item.canonical_name}'")