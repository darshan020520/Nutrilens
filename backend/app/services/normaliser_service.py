# app/domain/normalizer/service.py
from app.schemas.normaliser import VerifyMatchResult

class NormalizerService:
    def __init__(self, llm_runtime):
        self.llm = llm_runtime

    async def verify_match(self, user_text: str, candidate_name: str) -> VerifyMatchResult:
        prompt = f"""
You are verifying whether a grocery item description refers to a given catalog item.

User text: "{user_text}"
Candidate item: "{candidate_name}"

Decide if they refer to the same item.
Return JSON with fields:
- is_match (bool)
- confidence (0 to 1)
- reasoning (string)
"""

        messages = [{"role": "user", "content": prompt}]

        return await self.llm.execute(
            ctx=None,
            model="gpt-4o-mini",
            messages=messages,
            schema=VerifyMatchResult
        )
