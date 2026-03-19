"""
MongoDB Prompt Registry - Stores and retrieves LLM prompt templates.

Implements IPromptRegistry using MongoDB for flexible prompt storage.

Document Schema:
{
    "slug": "verify_match",
    "version": 1,
    "active": true,
    "messages": [
        {"role": "system", "content": "You are a grocery item matcher..."},
        {"role": "user", "content": "User entered: {user_text}\n\nCandidates:\n{candidates}"}
    ],
    "config": {
        "model": "gpt-4o-mini",
        "temperature": 0,
        "max_tokens": 500,
        "retries": 2
    },
    "created_at": datetime,
    "updated_at": datetime
}
"""
import logging
from typing import Dict, Any, List, Tuple
from motor.motor_asyncio import AsyncIOMotorClient
from app.infrastructure.normalization.interfaces import IPromptRegistry

logger = logging.getLogger(__name__)


class MongoPromptRegistry(IPromptRegistry):
    """
    MongoDB-based prompt registry.

    Stores prompt templates with:
    - slug: Unique identifier (e.g., "verify_match", "estimate_nutrition")
    - messages: Template messages with {variable} placeholders
    - config: Model settings (model, temperature, max_tokens, retries)
    - version: For tracking prompt iterations
    - active: Only active=True prompts are fetched

    Template Rendering:
    Uses Python's str.format() for variable substitution.
    Template: "User entered: {user_text}"
    Variables: {"user_text": "red capsicum"}
    Result: "User entered: red capsicum"
    """

    def __init__(
        self,
        client: AsyncIOMotorClient,
        database: str,
        collection: str = "llm_prompts"
    ):
        """
        Args:
            client: Motor async MongoDB client
            database: Database name
            collection: Collection name (default: "llm_prompts")
        """
        self.db = client[database]
        self.collection = self.db[collection]

    async def get_rendered_prompt(
        self,
        slug: str,
        variables: Dict[str, Any]
    ) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
        """
        Fetch template by slug and render with variables.

        Args:
            slug: Unique identifier for the prompt
            variables: Values to inject into template placeholders

        Returns:
            Tuple of:
            - messages: List of rendered messages ready for LLM
            - config: Model settings dict

        Raises:
            KeyError: If no active prompt found for slug
            KeyError: If template variable is missing from variables dict
        """
        # Fetch active template for this slug
        template = await self.collection.find_one(
            {"slug": slug, "active": True},
            sort=[("version", -1)]  # Get highest version if multiple active
        )

        if not template:
            logger.error(f"Prompt template not found: {slug}")
            raise KeyError(f"Prompt template not found: {slug}")

        # Render each message with variables
        rendered_messages = []
        for msg in template["messages"]:
            try:
                # Convert non-string variables to string for template rendering
                string_variables = {
                    k: str(v) if not isinstance(v, str) else v
                    for k, v in variables.items()
                }
                rendered_content = msg["content"].format(**string_variables)
                rendered_messages.append({
                    "role": msg["role"],
                    "content": rendered_content
                })
            except KeyError as e:
                logger.error(f"Missing template variable for '{slug}': {e}")
                raise KeyError(f"Missing template variable for '{slug}': {e}")

        logger.debug(f"Rendered prompt '{slug}' with {len(rendered_messages)} messages")

        return rendered_messages, template["config"]

    async def get_prompt_metadata(self, slug: str) -> Dict[str, Any]:
        """
        Get prompt metadata without rendering (for debugging/admin).

        Args:
            slug: Prompt identifier

        Returns:
            Full prompt document (excluding _id)
        """
        template = await self.collection.find_one(
            {"slug": slug, "active": True},
            projection={"_id": 0}
        )

        if not template:
            raise KeyError(f"Prompt template not found: {slug}")

        return template

    async def list_prompts(self) -> List[Dict[str, Any]]:
        """
        List all active prompts (for admin/debugging).

        Returns:
            List of prompt summaries (slug, version, model)
        """
        cursor = self.collection.find(
            {"active": True},
            projection={"_id": 0, "slug": 1, "version": 1, "config.model": 1}
        )

        prompts = []
        async for doc in cursor:
            prompts.append({
                "slug": doc["slug"],
                "version": doc["version"],
                "model": doc.get("config", {}).get("model", "unknown")
            })

        return prompts
