"""LLM Matcher - Verifies matches using LLM reasoning"""
import logging
import json
from app.infrastructure.normalization.chain.base_handler import IMatchHandler
from app.infrastructure.normalization.chain.match_context import MatchContext
from app.core.llm_orchestrator import LLMOrchestrator
from app.schemas.normaliser import MatchOrIdentifyResult

logger = logging.getLogger(__name__)


class LLMMatcherHandler(IMatchHandler):
    """
    Handler for LLM-based match verification and unknown item detection.

    Responsibilities:
    - Take candidates from context.vector_candidates
    - Use LLM to verify if any candidate is a true match
    - If no match, detect and identify unknown items
    - Mark context as matched OR mark unknown_item_detected

    Chain Position: Last matcher in chain (after ExactMatcher, AliasMatcher, VectorMatcher)
    Chain Behavior: This is the final handler - always stops chain

    Prompt: See PROMPTS_REGISTRY.md for "match_or_identify" prompt template
    """

    def __init__(self, llm_orchestrator: LLMOrchestrator, confidence_threshold: float = 0.7):
        """
        Args:
            llm_orchestrator: LLMOrchestrator for LLM calls
            confidence_threshold: Minimum confidence (0-1)
        """
        super().__init__()
        self.orchestrator = llm_orchestrator
        self.confidence_threshold = confidence_threshold

    async def _process(self, context: MatchContext) -> None:
        """
        Use LLM to verify vector candidates OR detect unknown items.

        Args:
            context: Shared context containing user_text, user_id, and vector_candidates
        """
        # Prepare top 3 candidates for LLM (empty list if no vector results)
        candidates = [
            {
                "item_id": c["item_id"],
                "item_name": c["item_name"],
                "similarity": c["similarity"]
            }
            for c in context.vector_candidates[:3]
        ] if context.vector_candidates else []

        context.add_log(f"LLMMatcher: Calling LLM with {len(candidates)} candidates")

        # Call orchestrator - prompts are in MongoDB registry
        # Slug: "match_or_identify" (see PROMPTS_REGISTRY.md)
        try:
            result = await self.orchestrator.run(
                user_id=context.user_id,
                slug="match_or_identify",
                variables={
                    "user_text": context.user_text,
                    "candidates": json.dumps(candidates, indent=2),
                    "has_candidates": len(candidates) > 0
                },
                response_model=MatchOrIdentifyResult
            )
        except Exception as e:
            context.add_log(f"LLMMatcher: LLM call failed - {e}")
            return

        # CASE 1: LLM found a match in candidates
        if result.matched and result.item_id and result.confidence >= self.confidence_threshold:
            # Find matched item name from candidates
            matched_candidate = next(
                (c for c in candidates if c["item_id"] == result.item_id),
                None
            )

            if matched_candidate:
                context.mark_matched(
                    item_id=result.item_id,
                    item_name=matched_candidate["item_name"],
                    confidence=result.confidence,
                    strategy="llm",
                    reasoning=result.reasoning
                )
                context.add_log(
                    f"LLMMatcher: Match verified '{context.user_text}' -> '{matched_candidate['item_name']}' "
                    f"(confidence: {result.confidence:.3f})"
                )
                return  # Chain terminates

        # CASE 2: LLM detected unknown food item
        if result.unknown_item and result.unknown_item.is_food_item and result.unknown_item.confidence >= 0.7:
            context.mark_unknown_item(
                item_name=result.unknown_item.name,
                category=result.unknown_item.category,
                confidence=result.unknown_item.confidence,
                reasoning=result.reasoning
            )
            context.add_log(
                f"LLMMatcher: Unknown item detected '{result.unknown_item.name}' "
                f"(category: {result.unknown_item.category}, confidence: {result.unknown_item.confidence:.3f})"
            )
            return  # Chain terminates

        # CASE 3: Neither matched nor valid food item
        unknown_confidence = result.unknown_item.confidence if result.unknown_item else 0
        context.add_log(
            f"LLMMatcher: No match and not a valid food item (confidence: {unknown_confidence:.3f})"
        )
