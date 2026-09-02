from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class DeckMatchResult:
    """One deck's match score against a collection, for search-result listings."""

    commander_name: str
    identity: str
    match_score: float
    owned_count: int
    deck_size: int

    @property
    def match_percentage(self) -> float:
        """match_score as a percentage, rounded to 2 decimal places."""
        return round(self.match_score * 100, 2)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict, including the computed match_percentage."""
        return asdict(self) | {"match_percentage": self.match_percentage}


@dataclass(frozen=True)
class ReplacementGroupResult:
    """Missing cards and their suggested replacements for one functional tag."""

    tag: str
    missing_cards: tuple[str, ...]
    replacements: tuple[str, ...]


@dataclass(frozen=True)
class DeckAnalysisResult:
    """Full analysis of a deck against a collection, including recommendations."""

    commander_name: str
    identity: str
    match_score: float
    owned_count: int
    missing_count: int
    missing_cards: tuple[str, ...]
    missing_by_tag: dict[str, tuple[str, ...]]
    replacements_by_tag: tuple[ReplacementGroupResult, ...] = ()
    owned_synergy_cards: tuple[str, ...] = ()
    same_type_replacements: dict[str, tuple[str, ...]] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @property
    def match_percentage(self) -> float:
        """match_score as a percentage, rounded to 2 decimal places."""
        return round(self.match_score * 100, 2)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict, expanding replacements_by_tag and including match_percentage."""
        return asdict(self) | {
            "match_percentage": self.match_percentage,
            "replacements_by_tag": [
                asdict(group) for group in self.replacements_by_tag
            ],
        }