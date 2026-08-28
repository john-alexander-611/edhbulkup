from __future__ import annotations

import io
from pathlib import Path

import httpx
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.schemas import (
    DeckAnalysisResponse,
    DeckMatchResponse,
    SearchQuery,
    UploadCollectionResponse,
)
from find_deck_matches import (
    filter_color_identity,
    filter_exclude_colors,
    get_decks,
)
from models.collection import Collection
from parse_input.parse_moxfield import parse_moxfield_csv
from services.deck_service import add_recommendations, analyze_deck, search_decks
from scryfall.cache_wrappers import ScryfallCache, TagCache

app = FastAPI(title="EDH Bulk Up", version="0.1.0")

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/search", response_model=list[DeckMatchResponse])
def search_commanders(
    color: str | None = Query(default=None),
    exclude: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
):
    collection = Collection(parse_moxfield_csv("parse_input/collection.csv"))
    filters = []
    if color:
        filters.append(filter_color_identity(color))
    if exclude:
        filters.append(filter_exclude_colors(exclude))

    matches = search_decks(
        get_decks().values(),
        collection,
        filters=filters,
        limit=limit,
    )
    return [
        DeckMatchResponse(
            commander_name=result.commander_name,
            identity=result.identity,
            match_score=result.match_score,
            match_percentage=result.match_percentage,
            owned_count=result.owned_count,
            deck_size=result.deck_size,
        )
        for result in matches
    ]


@app.get("/api/commanders/{commander_name}", response_model=DeckAnalysisResponse)
async def commander_analysis(commander_name: str):
    deck_map = get_decks()
    deck = deck_map.get(commander_name)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Commander not found: {commander_name}")

    async with httpx.AsyncClient(timeout=20) as client:
        from create_cache.edhrec_raw import fetch_commander_page_categories

        deck.set_categories(await fetch_commander_page_categories(client, deck.name))

    collection = Collection(parse_moxfield_csv("parse_input/collection.csv"))
    analysis = analyze_deck(deck, collection)
    scryfall_cache = ScryfallCache()
    tag_cache = TagCache()
    try:
        analysis = add_recommendations(analysis, deck, collection, scryfall_cache, tag_cache)
    finally:
        scryfall_cache.close()
        tag_cache.close()

    return DeckAnalysisResponse(
        commander_name=analysis.commander_name,
        identity=analysis.identity,
        match_score=analysis.match_score,
        match_percentage=analysis.match_percentage,
        owned_count=analysis.owned_count,
        missing_count=analysis.missing_count,
        missing_cards=list(analysis.missing_cards),
        missing_by_tag={tag: list(cards) for tag, cards in analysis.missing_by_tag.items()},
        replacements_by_tag=[
            {
                "tag": group.tag,
                "missing_cards": list(group.missing_cards),
                "replacements": list(group.replacements),
            }
            for group in analysis.replacements_by_tag
        ],
        owned_synergy_cards=list(analysis.owned_synergy_cards),
        same_type_replacements={
            card: list(names) for card, names in analysis.same_type_replacements.items()
        },
        warnings=list(analysis.warnings),
    )


@app.post("/api/collection/upload", response_model=UploadCollectionResponse)
def upload_collection(file: UploadFile = File(...)):
    content = file.file.read()
    parsed = parse_moxfield_csv(io.StringIO(content.decode("utf-8-sig")))
    collection = Collection(parsed)
    return UploadCollectionResponse(
        owned_count=len(collection.names),
        sample_cards=sorted(collection.names)[:10],
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
