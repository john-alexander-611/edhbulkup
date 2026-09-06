from __future__ import annotations

import asyncio
import io
import logging
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import httpx
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from download_caches import ensure_caches, get_latest_release_id
from app.schemas import (
    CardPresentationResponse,
    DeckAnalysisResponse,
    DecklistCardResponse,
    DeckMatchResponse,
    SearchQuery,
    SearchResultsResponse,
    UploadCollectionResponse,
)
from find_deck_matches import (
    excluded_commanders,
    filter_color_identity,
    filter_contains_colors,
    filter_exclude_colors,
    filter_excluded_commanders,
    filter_face_commanders,
    filter_partners,
    filter_commander_name,
    get_commander_suggestions,
    get_decks,
)
from models.collection import Collection
from parse_input.parse_moxfield import parse_moxfield_csv, parse_plaintext_collection
from services.deck_service import add_recommendations, analyze_deck, count_deck_matches, search_decks
from scryfall.cache_wrappers import ScryfallCache, TagCache

logger = logging.getLogger(__name__)


def cache_auto_refresh_enabled() -> bool:
    """Return whether this backend should synchronize published cache releases."""
    return os.getenv("CACHE_AUTO_REFRESH", "false").lower() in {"1", "true", "yes"}


def cache_refresh_interval_seconds() -> int:
    """Return the release polling interval, defaulting to three hours."""
    return max(60, int(os.getenv("CACHE_REFRESH_INTERVAL_SECONDS", "10800")))


async def refresh_caches_when_release_changes(release_id: int) -> None:
    """Poll GitHub and replace local cache files after a new release is published."""
    while True:
        await asyncio.sleep(cache_refresh_interval_seconds())
        try:
            latest_release_id = await asyncio.to_thread(get_latest_release_id)
            if latest_release_id != release_id:
                release_id = await asyncio.to_thread(ensure_caches, force=True)
                logger.info("Refreshed local caches from GitHub release %s", release_id)
        except Exception:
            logger.exception("Unable to refresh caches; keeping the current local caches")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Optionally synchronize cache assets during the backend lifecycle."""
    refresh_task = None
    if cache_auto_refresh_enabled():
        try:
            release_id = await asyncio.to_thread(ensure_caches, force=True)
            logger.info("Loaded local caches from GitHub release %s", release_id)
            refresh_task = asyncio.create_task(refresh_caches_when_release_changes(release_id))
        except Exception:
            logger.exception("Unable to load current caches at startup; using local caches")
    try:
        yield
    finally:
        if refresh_task:
            refresh_task.cancel()
            with suppress(asyncio.CancelledError):
                await refresh_task

def get_allowed_origins() -> list[str]:
    """CORS-allowed origins from CORS_ALLOWED_ORIGINS env var, or a localhost dev default."""
    configured = os.getenv("CORS_ALLOWED_ORIGINS", "")
    origins = [
        origin.strip().rstrip("/")
        for origin in configured.split(",")
        if origin.strip()
    ]
    if origins:
        return origins
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://0.0.0.0:3000",
        "https://localhost:3000",
        "https://127.0.0.1:3000",
    ]


app = FastAPI(title="EDH Bulk Up", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.vercel\.app/.*",
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


def humanize_tag_label(tag: str) -> str:
    """Convert a functional tag slug (e.g. "card-advantage") to a display label (e.g. "Card Advantage")."""
    if not tag:
        return tag

    label_map = {
        "ramp": "Ramp",
        "removal": "Removal",
        "card-advantage": "Card Advantage",
        "tutor": "Tutor",
        "hate": "Hate",
        "burn": "Burn",
        "lifegain": "Life Gain",
        "death-trigger": "Death Trigger",
        "recursion": "Recursion",
    }

    normalized = tag.strip().lower()
    return label_map.get(normalized, " ".join(part[:1].upper() + part[1:] for part in normalized.replace("_", "-").replace("-", " ").split()))


def build_card_details(cards: list[str] | tuple[str, ...], lookup):
    """Resolve card names to CardPresentationResponse objects via lookup, deduped and sorted.

    Args:
        cards: Card names to resolve.
        lookup: Callable(list[str]) -> dict[str, dict] mapping name to display metadata.

    Returns:
        list[CardPresentationResponse]: Resolved cards, skipping any lookup misses.
    """
    card_names = sorted(dict.fromkeys(card for card in cards if card and card.strip()))
    if not card_names:
        return []
    card_meta_lookup = lookup(card_names)
    return [
        CardPresentationResponse(
            name=card_name,
            display_name=card_meta_lookup[card_name]["display_name"],
            image_url=card_meta_lookup[card_name]["image_url"],
            usd_price=card_meta_lookup[card_name].get("usd_price"),
            tcgplayer_id=card_meta_lookup[card_name].get("tcgplayer_id"),
        )
        for card_name in card_names
        if card_name in card_meta_lookup and card_meta_lookup[card_name] is not None
    ]


def get_uploaded_collection() -> Collection:
    """Return the collection uploaded in this app session.

    Raises:
        HTTPException: 400 if no collection has been uploaded yet.
    """
    collection = getattr(app.state, "collection", None)
    if collection is None:
        raise HTTPException(
            status_code=400,
            detail="Upload a collection CSV before searching or analyzing commanders.",
        )
    return collection

def clear_uploaded_collection() -> None:
    """Remove the uploaded collection from app state, if present."""
    if hasattr(app.state, "collection"):
        delattr(app.state, "collection")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check endpoint."""
    return {"status": "ok"}


@app.get("/api/search", response_model=SearchResultsResponse)
def search_commanders(
    color: str | None = Query(default=None),
    identity: str | None = Query(default=None),
    contains: str | None = Query(default=None),
    exclude: str | None = Query(default=None),
    name: str | None = Query(default=None),
    identity_colors: list[str] = Query(default=[]),
    contains_colors: list[str] = Query(default=[]),
    exclude_colors: list[str] = Query(default=[]),
    exclude_face: bool = Query(default=False),
    exclude_partners: bool = Query(default=False),
    only_owned_commanders: bool = Query(default=False),
    exclude_commanders: list[str] = Query(default=[]),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    """Search cached decks by color/name filters, matched against the uploaded collection.

    Raises:
        HTTPException: 400 if no collection has been uploaded yet.
    """
    collection = get_uploaded_collection()
    filters = []

    if name:
        filters.append(filter_commander_name(name))
    if color:
        filters.append(filter_color_identity(color))
    selected_identity = "".join(identity_colors)
    selected_contains = "".join(contains_colors)
    selected_exclude = "".join(exclude_colors)
    if identity or selected_identity:
        filters.append(filter_color_identity(identity or selected_identity))
    if contains or selected_contains:
        filters.append(filter_contains_colors(contains or selected_contains))
    if exclude or selected_exclude:
        filters.append(filter_exclude_colors(exclude or selected_exclude))
    if exclude_face:
        filters.append(filter_face_commanders)
    if exclude_partners:
        filters.append(filter_partners)
    if only_owned_commanders:
        filters.append(lambda deck: deck.commander.name in collection)

    excluded_names = {name.strip() for name in exclude_commanders if name.strip()}
    if excluded_names:
        filters.append(filter_excluded_commanders(excluded_names))

    all_decks = get_decks().values()
    matches = search_decks(
        all_decks,
        collection,
        filters=filters,
        limit=limit,
        offset=offset,
    )
    total = count_deck_matches(all_decks, filters=filters)
    scryfall_cache = ScryfallCache()
    try:
        serialized_matches = []
        for result in matches:
            commander_meta = scryfall_cache.get_card_display(result.commander_name)
            serialized_matches.append(
                DeckMatchResponse(
                    commander_name=result.commander_name,
                    identity=result.identity,
                    match_score=result.match_score,
                    match_percentage=result.match_percentage,
                    owned_count=result.owned_count,
                    deck_size=result.deck_size,
                    image_url=commander_meta["image_url"],
                )
            )
        return SearchResultsResponse(results=serialized_matches, total=total)
    finally:
        scryfall_cache.close()


@app.get("/api/commanders/suggestions")
def commander_suggestions(q: str = Query(default="")):
    """Return up to 15 cached commander names matching query q."""
    return {"suggestions": get_commander_suggestions(q, limit=15)}


@app.get("/api/commanders/{commander_name}", response_model=DeckAnalysisResponse)
async def commander_analysis(commander_name: str):
    """Fetch EDHREC data for a commander and return a full analysis against the uploaded collection.

    Raises:
        HTTPException: 404 if commander_name has no cached deck; 400 if no collection uploaded.
    """
    deck_map = get_decks()
    deck = deck_map.get(commander_name)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Commander not found: {commander_name}")

    async with httpx.AsyncClient(timeout=20) as client:
        from create_cache.edhrec_raw import fetch_commander_page_categories

        deck.set_categories(await fetch_commander_page_categories(client, deck.name))

    collection = get_uploaded_collection()
    analysis = analyze_deck(deck, collection)
    scryfall_cache = ScryfallCache()
    tag_cache = TagCache()
    try:
        analysis = add_recommendations(analysis, deck, collection, scryfall_cache, tag_cache)
        average_decklist = [
            DecklistCardResponse(
                name=card_name,
                display_name=card_meta["display_name"],
                image_url=card_meta["image_url"],
                usd_price=card_meta.get("usd_price"),
                tcgplayer_id=card_meta.get("tcgplayer_id"),
                quantity=quantity,
                owned_quantity=min(collection.quantity(card_name), quantity),
                owned=collection.quantity(card_name) >= quantity,
                card_type=scryfall_cache.get_primary_card_type(
                    scryfall_cache.get_type_line(card_name) or ""
                ) or "other",
            )
            for card_name, quantity in deck.average_decklist_counts
            for card_meta in [scryfall_cache.get_card_display(card_name)]
        ]
        missing_card_details = build_card_details(
            analysis.missing_cards,
            lambda names: scryfall_cache.get_many_card_displays(names),
        )
        replacements_by_tag = []
        for group in analysis.replacements_by_tag:
            group_missing_card_details = build_card_details(
                group.missing_cards,
                lambda names: {name: scryfall_cache.get_card_display(name) for name in names},
            )
            replacement_details = [
                CardPresentationResponse(
                    name=card_name,
                    display_name=card_meta["display_name"],
                    image_url=card_meta["image_url"],
                    usd_price=card_meta["usd_price"],
                    tcgplayer_id=card_meta.get("tcgplayer_id"),
                )
                for card_name in group.replacements
                for card_meta in [scryfall_cache.get_card_display(card_name)]
            ]
            replacements_by_tag.append(
                {
                    "tag": humanize_tag_label(group.tag),
                    "missing_cards": list(group.missing_cards),
                    "missing_card_details": group_missing_card_details,
                    "replacements": list(group.replacements),
                    "replacement_details": replacement_details,
                }
            )
        commander_meta = scryfall_cache.get_card_display(analysis.commander_name)
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
        missing_card_details=missing_card_details,
        average_decklist=average_decklist,
        missing_by_tag={tag: list(cards) for tag, cards in analysis.missing_by_tag.items()},
        replacements_by_tag=replacements_by_tag,
        owned_synergy_cards=list(analysis.owned_synergy_cards),
        same_type_replacements={
            card: list(names) for card, names in analysis.same_type_replacements.items()
        },
        warnings=list(analysis.warnings),
        image_url=commander_meta["image_url"],
        usd_price=commander_meta.get("usd_price"),
        tcgplayer_id=commander_meta.get("tcgplayer_id"),
    )


@app.post("/api/collection/upload", response_model=UploadCollectionResponse)
def upload_collection(file: UploadFile = File(...)):
    """Parse an uploaded collection file (.txt plaintext or Moxfield CSV) and store it in app state.

    Raises:
        HTTPException: 400 if the file is empty, not valid UTF-8 text, or has no
            parseable card rows/lines.
    """
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail=f"'{file.filename}' is empty. Upload a non-empty CSV or TXT file.")

    try:
        decoded_content = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail=f"'{file.filename}' isn't a valid text file. Export it as UTF-8 CSV or TXT and try again.",
        )

    skipped: list[str] = []
    try:
        if Path(file.filename or "").suffix.lower() == ".txt":
            parsed = parse_plaintext_collection(io.StringIO(decoded_content), skipped=skipped)
        else:
            parsed = parse_moxfield_csv(io.StringIO(decoded_content), skipped=skipped)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"'{file.filename}': {exc}")

    warnings = []
    if skipped:
        examples = "; ".join(skipped[:5])
        warnings.append(
            f"{len(skipped)} row(s) couldn't be read and were skipped (e.g. {examples})."
        )

    collection = Collection(parsed)
    app.state.collection = collection
    return UploadCollectionResponse(
        owned_count=len(collection.names),
        sample_cards=sorted(collection.names)[:10],
        warnings=warnings,
    )
    
@app.post("/api/collection/clear")
def clear_collection():
    """Clear the uploaded collection from app state."""
    clear_uploaded_collection()
    return {"status": "success"}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("APP_ENV", "production") != "production"
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)
