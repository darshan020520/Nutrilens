"""Match Context - Shared state object for Chain of Responsibility"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class MatchContext:
    """
    Shared context object that flows through the matcher chain

    This context accumulates state as it passes through each handler.
    Each handler can read from and write to this context to make decisions
    and communicate results.

    Chain of Responsibility Principle:
    - Single request object passed through entire chain
    - Handlers modify context state based on their logic
    - Later handlers can see results from earlier handlers
    """

    # INPUT: Original user input
    user_text: str
    user_id: int = 0  # User ID for token budget tracking

    # STATE: Match result (set by successful matcher)
    matched: bool = False
    item_id: Optional[int] = None
    item_name: Optional[str] = None
    confidence: float = 0.0
    match_strategy: Optional[str] = None  # "exact", "alias", "vector", "llm"

    # STATE: Intermediate data (used by handlers for decisions)
    item_cache: Optional[Dict[str, int]] = None  # name/alias -> item_id mapping
    embedding: Optional[List[float]] = None  # User text embedding
    vector_candidates: Optional[List[Dict[str, Any]]] = field(default_factory=list)  # Vector search results

    # STATE: Metadata and reasoning
    reasoning: Optional[str] = None  # Why this match was chosen
    processing_log: List[str] = field(default_factory=list)  # Audit trail

    # STATE: Unknown item detection (when LLM identifies item not in database)
    unknown_item_detected: bool = False
    unknown_item_name: Optional[str] = None  # Normalized name (e.g., "dragon_fruit")
    unknown_item_category: Optional[str] = None  # Category (e.g., "fruits")
    unknown_item_confidence: float = 0.0  # LLM confidence this is a real food item

    def mark_matched(
        self,
        item_id: int,
        item_name: str,
        confidence: float,
        strategy: str,
        reasoning: Optional[str] = None
    ):
        """
        Mark context as successfully matched

        Args:
            item_id: Matched item ID
            item_name: Matched item name
            confidence: Match confidence (0-1)
            strategy: Strategy used ("exact", "alias", "vector", "llm")
            reasoning: Optional explanation
        """
        self.matched = True
        self.item_id = item_id
        self.item_name = item_name
        self.confidence = confidence
        self.match_strategy = strategy
        if reasoning:
            self.reasoning = reasoning

    def mark_unknown_item(
        self,
        item_name: str,
        category: str,
        confidence: float,
        reasoning: Optional[str] = None
    ):
        """
        Mark context as having detected an unknown item

        Args:
            item_name: Normalized item name (e.g., "dragon_fruit")
            category: Item category (e.g., "fruits")
            confidence: LLM confidence this is a real food item (0-1)
            reasoning: Optional explanation
        """
        self.unknown_item_detected = True
        self.unknown_item_name = item_name
        self.unknown_item_category = category
        self.unknown_item_confidence = confidence
        if reasoning:
            self.reasoning = reasoning

    def add_log(self, message: str):
        """Add entry to processing log"""
        self.processing_log.append(message)

    def should_continue(self) -> bool:
        """
        Determine if chain should continue processing

        Returns:
            True if chain should continue, False if processing complete
        """
        # Stop if already matched
        return not self.matched