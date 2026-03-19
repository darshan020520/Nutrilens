from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class MatchContext:

    user_text: str
    user_id: int = 0

    matched: bool = False
    item_id: Optional[int] = None
    item_name: Optional[str] = None
    confidence: float = 0.0
    match_strategy: Optional[str] = None  


    item_cache: Optional[Dict[str, int]] = None  
    embedding: Optional[List[float]] = None
    vector_candidates: Optional[List[Dict[str, Any]]] = field(default_factory=list) 

    reasoning: Optional[str] = None
    processing_log: List[str] = field(default_factory=list)  
    unknown_item_detected: bool = False
    unknown_item_name: Optional[str] = None
    unknown_item_category: Optional[str] = None
    unknown_item_confidence: float = 0.0 

    def mark_matched(
        self,
        item_id: int,
        item_name: str,
        confidence: float,
        strategy: str,
        reasoning: Optional[str] = None
    ):

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
        return not self.matched