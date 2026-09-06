from __future__ import annotations

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    color: str | None = Field(default=None, description="Optional color identity filter, e.g. WUB")
    exclude: str | None = Field(default=None, description="Optional excluded colors, e.g. UB")
    limit: int = Field(default=10, ge=1, le=50)


class CardPresentationResponse(BaseModel):
    name: str
    display_name: str
    image_url: str | None = None
    usd_price: float | None = None


class DecklistCardResponse(CardPresentationResponse):
    quantity: int
    owned_quantity: int
    owned: bool
    card_type: str


class DeckMatchResponse(BaseModel):
    commander_name: str
    identity: str
    match_score: float
    match_percentage: float
    owned_count: int
    deck_size: int
    image_url: str | None = None


class SearchResultsResponse(BaseModel):
    results: list[DeckMatchResponse]
    total: int


class ReplacementGroupResponse(BaseModel):
    tag: str
    missing_cards: list[str]
    missing_card_details: list[CardPresentationResponse] = []
    replacements: list[str]
    replacement_details: list[CardPresentationResponse] = []


class DeckAnalysisResponse(BaseModel):
    commander_name: str
    identity: str
    match_score: float
    match_percentage: float
    owned_count: int
    missing_count: int
    missing_cards: list[str]
    missing_card_details: list[CardPresentationResponse] = []
    average_decklist: list[DecklistCardResponse] = []
    missing_by_tag: dict[str, list[str]]
    replacements_by_tag: list[ReplacementGroupResponse] = []
    owned_synergy_cards: list[str] = []
    same_type_replacements: dict[str, list[str]] = {}
    warnings: list[str] = []
    image_url: str | None = None


class UploadCollectionResponse(BaseModel):
    """Result of parsing an uploaded collection file."""

    owned_count: int
    warnings: list[str] = []
