"""Normalizer schemas for LLM structured outputs"""
from pydantic import BaseModel
from typing import Optional


class VerifyMatchResult(BaseModel):
    """Response schema for match verification"""
    is_match: bool
    confidence: float
    reasoning: str


class MatchResult(BaseModel):
    """Result of item matching"""
    item_id: Optional[int]
    confidence: float
    source: str  # "exact", "alias", "vector", "llm"
    reasoning: str


class ConvertToGramsResult(BaseModel):
    """Response schema for unit-to-grams conversion"""
    grams: float
    confidence: float
    reasoning: str


class ExtractStructureResult(BaseModel):
    """Response schema for structure extraction from text"""
    quantity: float
    unit: str
    item_text: str


class UnknownItemInfo(BaseModel):
    """Nested schema for unknown item detection"""
    name: str  # Normalized name, e.g., "dragon_fruit"
    category: str  # e.g., "fruits", "vegetables", "dairy"
    is_food_item: bool  # False for garbage input like "asdfgh"
    confidence: float  # 0.0-1.0


class MatchOrIdentifyResult(BaseModel):
    """
    Response schema for LLM match verification and unknown item detection.

    Used by LLMMatcherHandler when vector candidates exist or when
    identifying completely unknown items.

    Three outcomes:
    1. matched=True, item_id=X: Item matched a candidate
    2. matched=False, unknown_item.is_food_item=True: Valid food not in DB
    3. matched=False, unknown_item.is_food_item=False: Garbage input
    """
    matched: bool
    item_id: Optional[int] = None  # ID from vector candidates if matched
    confidence: float
    reasoning: str
    unknown_item: Optional[UnknownItemInfo] = None