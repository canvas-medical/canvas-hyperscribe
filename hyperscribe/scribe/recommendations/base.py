from __future__ import annotations

from abc import ABC, abstractmethod

from canvas_sdk.clients.llms.libraries import LlmAnthropic

from hyperscribe.scribe.backend.models import ClinicalNote, CommandProposal


class BaseRecommender(ABC):
    """One file per command type. Subclasses define their schema, prompt, and code resolution."""

    @abstractmethod
    def recommend(self, note: ClinicalNote, client: LlmAnthropic) -> list[CommandProposal]:
        """Extract structured recommendations for this command type from the note."""
        ...
