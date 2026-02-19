from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class IEmbeddingService(ABC):

    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        pass

    @abstractmethod
    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        pass


class IEmbeddingAdapter(ABC):

    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        pass

    @abstractmethod
    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        pass


class IPromptRegistry(ABC):

    @abstractmethod
    async def get_rendered_prompt(
        self,
        slug: str,
        variables: Dict[str, Any]
    ) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
        pass


class ITokenGovernor(ABC):
    @abstractmethod
    async def reserve(self, user_id: int, amount: int, limit: int) -> bool:
        pass

    @abstractmethod
    async def refund(self, user_id: int, amount: int) -> None:
        pass


class ILLMAdapter(ABC):

    @abstractmethod
    async def execute(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[T],
        config: Dict[str, Any]
    ) -> Tuple[T, int]:
        pass