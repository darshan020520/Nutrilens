"""LLM Matcher - Verifies matches using LLM reasoning"""
import logging
import json
from app.infrastructure.normalization.chain.base_handler import IMatchHandler
from app.infrastructure.normalization.chain.match_context import MatchContext
from app.core.llm_orchestrator import LLMOrchestrator
from app.schemas.normaliser import MatchOrIdentifyResult

logger = logging.getLogger(__name__)


class LLMMatcherHandler(IMatchHandler):

    def __init__(self, llm_orchestrator: LLMOrchestrator, confidence_threshold: float = 0.7):

        super().__init__()
        self.orchestrator = llm_orchestrator
        self.confidence_threshold = confidence_threshold

    async def _process(self, context: MatchContext) -> None:

        candidates = [
            {
                "item_id": c["item_id"],
                "item_name": c["item_name"],
                "similarity": c["similarity"]
            }
            for c in context.vector_candidates[:3]
        ] if context.vector_candidates else []


        print(f"  [LLMMatcher] user_text='{context.user_text}', candidates_count={len(candidates)}")
        for c in candidates:
            print(f"    candidate: id={c['item_id']}, name='{c['item_name']}', sim={c['similarity']:.4f}")

        context.add_log(f"LLMMatcher: Calling LLM with {len(candidates)} candidates")

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
            print(f"  [LLMMatcher] RESULT: matched={result.matched}, item_id={result.item_id}, confidence={result.confidence}, reasoning='{result.reasoning}'")
            if result.unknown_item:
                print(f"  [LLMMatcher] UNKNOWN: name='{result.unknown_item.name}', category='{result.unknown_item.category}', is_food={result.unknown_item.is_food_item}, conf={result.unknown_item.confidence}")
        except Exception as e:
            context.add_log(f"LLMMatcher: LLM call failed - {e}")
            return

        if result.matched and result.item_id and result.confidence >= self.confidence_threshold:
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
                return


        if result.unknown_item and result.unknown_item.is_food_item and result.unknown_item.confidence >= 0.7:
            print(result.unknown_item)
            context.mark_unknown_item(
                item_name=result.unknown_item.name,
                category=result.unknown_item.category,
                confidence=result.unknown_item.confidence
            )
            context.add_log(
                f"LLMMatcher: Unknown item detected '{result.unknown_item.name}' "
                f"(category: {result.unknown_item.category}, confidence: {result.unknown_item.confidence:.3f})"
            )
            return

        unknown_confidence = result.unknown_item.confidence if result.unknown_item else 0
        context.add_log(
            f"LLMMatcher: No match and not a valid food item (confidence: {unknown_confidence:.3f})"
        )
