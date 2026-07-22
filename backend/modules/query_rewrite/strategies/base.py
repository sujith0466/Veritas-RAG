"""Abstract Base class for all rewrite strategies — Phase 8."""

from abc import ABC, abstractmethod

from backend.modules.query_rewrite.schemas.rewrite_dto import (
    RewriteRequestDTOv2, RewriteResultDTO, RewriteStrategy)


class BaseRewriteStrategy(ABC):
    """Abstract base for all query rewrite strategies."""

    @abstractmethod
    def rewrite(self, request: RewriteRequestDTOv2) -> RewriteResultDTO:
        """Transform the query and return a RewriteResultDTO."""
        ...

    def get_strategy_name(self) -> RewriteStrategy:
        raise NotImplementedError
