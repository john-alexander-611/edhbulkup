"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import { getCommanderAnalysis, type CardPresentation, type DeckAnalysis, type DecklistCard } from "@/lib/api";
import { tcgplayerCardUrl, tcgplayerMassEntryUrl } from "@/lib/tcgplayer";
import styles from "./page.module.css";

function formatTagLabel(tag: string) {
  const labelMap: Record<string, string> = {
    ramp: "Ramp",
    removal: "Removal",
    "card-advantage": "Card Advantage",
    tutor: "Tutor",
    hate: "Hate",
    burn: "Burn",
    lifegain: "Life Gain",
    "death-trigger": "Death Trigger",
    recursion: "Recursion",
  };

  const normalized = tag.trim().toLowerCase();
  return labelMap[normalized] ?? normalized
    .replace(/[_-]+/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

const decklistTypeOrder = ["commander", "creature", "instant", "sorcery", "artifact", "enchantment", "planeswalker", "battle", "land", "other"];

function groupDecklist(cards: DecklistCard[], commanderName: string) {
  return cards.reduce<Record<string, DecklistCard[]>>((groups, card) => {
    const type = card.name === commanderName.toLowerCase() ? "commander" : card.card_type;
    (groups[type] ??= []).push(card);
    return groups;
  }, {});
}

type DecklistTypeGroup = { type: string; cards: DecklistCard[] };

// Split into two fixed columns ourselves instead of relying on CSS multi-column balancing,
// which reflows (and jumps cards between columns) whenever a hover preview changes layout.
function splitDecklistColumns(cards: DecklistCard[], commanderName: string): DecklistTypeGroup[][] {
  const grouped = groupDecklist(cards, commanderName);
  const groups = decklistTypeOrder
    .map((type) => ({ type, cards: grouped[type] }))
    .filter((group): group is DecklistTypeGroup => Boolean(group.cards?.length));

  const columns: DecklistTypeGroup[][] = [[], []];
  const columnLines = [0, 0];
  for (const group of groups) {
    const targetColumn = columnLines[0] <= columnLines[1] ? 0 : 1;
    columns[targetColumn].push(group);
    columnLines[targetColumn] += group.cards.length + 1;
  }
  return columns;
}

type BudgetLimit = "any" | "five" | "one";

const budgetLimits: Record<BudgetLimit, number | null> = {
  any: null,
  five: 5,
  one: 1,
};

type LightboxState = {
  cards: CardPresentation[];
  index: number;
  title?: string;
};

export default function CommanderPage() {
  const params = useParams<{ commanderName?: string | string[] }>();
  const [analysis, setAnalysis] = useState<DeckAnalysis | null>(null);
  const [error, setError] = useState("");
  const [expandedSuggestionGroups, setExpandedSuggestionGroups] = useState<Record<string, boolean>>({});
  const [budgetLimit, setBudgetLimit] = useState<BudgetLimit>("any");
  const [lightbox, setLightbox] = useState<LightboxState | null>(null);

  const commanderName = Array.isArray(params.commanderName)
    ? params.commanderName[0]
    : params.commanderName;

  useEffect(() => {
    if (!commanderName) return;

    const safeCommanderName = decodeURIComponent(commanderName);

    getCommanderAnalysis(safeCommanderName)
      .then(setAnalysis)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Unable to load commander."));
  }, [commanderName]);

  if (error) return <main className={styles.page}><a href="/">Back to search</a><p>{error}</p></main>;
  if (!analysis) return <main className={styles.page}><a href="/">Back to search</a><p>Loading commander analysis...</p></main>;

  const missingCards = analysis.missing_card_details.map((card) => ({
    name: card.name,
    quantity: analysis.average_decklist.find((deckCard) => deckCard.name === card.name)?.quantity ?? 1,
  }));

  const commanderCard: CardPresentation = {
    name: analysis.commander_name,
    display_name: analysis.commander_name,
    image_url: analysis.image_url,
    usd_price: analysis.usd_price ?? analysis.average_decklist.find((deckCard) => deckCard.name.toLowerCase() === analysis.commander_name.toLowerCase())?.usd_price ?? null,
    tcgplayer_id: analysis.tcgplayer_id ?? analysis.average_decklist.find((deckCard) => deckCard.name.toLowerCase() === analysis.commander_name.toLowerCase())?.tcgplayer_id ?? null,
  };

  return <main className={styles.page}>
    <header className={styles.appHeader}>
      <Link className={styles.appBrand} href="/">
        <Image className={styles.logo} src="/edh_bulk_up_logo_v3.png" alt="EDH Bulk Up" width={360} height={180} priority />
        <span>Find Decks Hidden in Your Bulk</span>
      </Link>
      <Link className={styles.backLink} href="/">Back to search</Link>
    </header>
    <header className={styles.header}>
      {analysis.image_url ? <button
        type="button"
        className={styles.commanderImageButton}
        onClick={() => setLightbox({ cards: [commanderCard], index: 0, title: "Commander" })}
        aria-label={`View ${analysis.commander_name}`}
      >
        <img className={styles.commanderImage} src={analysis.image_url} alt={analysis.commander_name} />
        <img className={styles.commanderImagePreview} src={analysis.image_url} alt="" />
      </button> : null}
      <div className={styles.headerText}>
        <p className={styles.eyebrow}>{analysis.identity} COMMANDER</p>
        <h1>{analysis.commander_name}</h1>
        <p>{analysis.match_percentage.toFixed(1)}% match · {analysis.owned_count} owned · {analysis.missing_count} missing</p>
      </div>
    </header>
    <section>
      <h2>Average Decklist</h2>
      <div className={styles.decklist}>
        {splitDecklistColumns(analysis.average_decklist ?? [], analysis.commander_name).map((groups, index) => (
          <div className={styles.decklistColumn} key={index}>
            {groups.map(({ type, cards }) => {
              const total = cards.reduce((sum, card) => sum + card.quantity, 0);
              const groupTitle = `Decklist · ${formatTagLabel(type)}`;
              return <div className={styles.decklistGroup} key={type}>
                <h3>{formatTagLabel(type)} ({total})</h3>
                <ul>{cards.map((card, cardIndex) => (
                  <DecklistCard
                    card={card}
                    key={card.name}
                    onSelect={() => setLightbox({ cards, index: cardIndex, title: groupTitle })}
                  />
                ))}</ul>
              </div>;
            })}
          </div>
        ))}
      </div>
    </section>
    <section>
      <div className={styles.missingHeader}>
        <h2>Missing cards</h2>
        {missingCards.length ? <a className={styles.buyButton} href={tcgplayerMassEntryUrl(missingCards)} target="_blank" rel="noreferrer"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="9" cy="21" r="1" /><circle cx="20" cy="21" r="1" /><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" /></svg>Buy all on TCGplayer</a> : null}
      </div>
      <ul className={styles.missingList}>{analysis.missing_card_details.map((card, cardIndex) => (
        <li key={card.name}>
          <strong>{analysis.average_decklist.find((deckCard) => deckCard.name === card.name)?.quantity ?? 1}</strong>
          <Card
            card={card}
            onSelect={() => setLightbox({ cards: analysis.missing_card_details, index: cardIndex, title: "Missing Cards" })}
          />
        </li>
      ))}</ul>
    </section>
    <section>
      <div className={styles.replacementHeader}>
        <h2>Replacement Recommendations by Category</h2>
        <fieldset className={styles.budgetOptions}>
          <legend>Budget</legend>
          <label><input type="radio" name="budget" value="any" checked={budgetLimit === "any"} onChange={() => setBudgetLimit("any")} /> No budget limit</label>
          <label><input type="radio" name="budget" value="five" checked={budgetLimit === "five"} onChange={() => setBudgetLimit("five")} /> $5 and under per card</label>
          <label><input type="radio" name="budget" value="one" checked={budgetLimit === "one"} onChange={() => setBudgetLimit("one")} /> $1 and under per card</label>
        </fieldset>
      </div>
      {analysis.replacements_by_tag.map((group) => {
      const isExpanded = expandedSuggestionGroups[group.tag];
      const maxPrice = budgetLimits[budgetLimit];
      const budgetedReplacements = maxPrice === null
        ? group.replacement_details
        : group.replacement_details.filter((card) => card.usd_price !== null && card.usd_price <= maxPrice);
      const visibleReplacements = isExpanded ? budgetedReplacements : budgetedReplacements.slice(0, 10);
      const hasMoreSuggestions = budgetedReplacements.length > 10 && !isExpanded;

      return <article className={styles.group} key={group.tag}><h3>Category: {formatTagLabel(group.tag)}</h3>
        <div className={styles.subsection}>
          <h4 className={styles.missingHeading}>Missing Cards</h4>
          {group.missing_card_details?.length ? (
            <CardList
              cards={group.missing_card_details}
              onSelect={(idx) => setLightbox({ cards: group.missing_card_details, index: idx, title: `Missing · ${formatTagLabel(group.tag)}` })}
            />
          ) : (
            <p>Missing: {group.missing_cards.join(", ") || "None"}</p>
          )}
        </div>
        <div className={styles.subsection}>
          <h4 className={styles.replacementHeading}>Suggested Replacements</h4>
          {visibleReplacements.length ? (
            <CardList
              cards={visibleReplacements}
              onSelect={(idx) => setLightbox({ cards: visibleReplacements, index: idx, title: `Suggested Replacements · ${formatTagLabel(group.tag)}` })}
            />
          ) : (
            <p>No suggestions meet this budget.</p>
          )}
          {hasMoreSuggestions ? (
            <button
              className={styles.moreSuggestions}
              type="button"
              onClick={() => setExpandedSuggestionGroups((groups) => ({ ...groups, [group.tag]: true }))}
            >
              More suggestions
            </button>
          ) : null}
        </div>
      </article>;
    })}</section>

    {lightbox && (
      <Lightbox
        state={lightbox}
        onClose={() => setLightbox(null)}
        onNavigate={(newIndex) => setLightbox((curr) => curr ? { ...curr, index: newIndex } : null)}
      />
    )}
  </main>;
}

function Card({ card, onSelect }: { card: CardPresentation; onSelect?: () => void }) {
  return <button type="button" className={styles.cardButton} onClick={onSelect}>
    <span>{card.display_name || card.name}</span>
    {card.image_url ? <img className={styles.cardPreview} src={card.image_url} alt="" /> : null}
  </button>;
}

function CardList({ cards, onSelect }: { cards: CardPresentation[]; onSelect?: (index: number) => void }) {
  return <ul className={styles.cardList}>{cards.map((card, index) => (
    <li key={card.name}><Card card={card} onSelect={() => onSelect?.(index)} /></li>
  ))}</ul>;
}

function DecklistCard({ card, onSelect }: { card: DecklistCard; onSelect?: () => void }) {
  return <li className={`${styles.decklistCard} ${card.owned ? "" : styles.missingCard}`}>
    <strong>{card.owned_quantity}/{card.quantity}</strong>
    <button type="button" className={styles.decklistButton} onClick={onSelect}>
      <span>{card.display_name || card.name}</span>
      {card.image_url ? <img className={styles.cardPreview} src={card.image_url} alt="" /> : null}
    </button>
  </li>;
}

function Lightbox({
  state,
  onClose,
  onNavigate,
}: {
  state: LightboxState;
  onClose: () => void;
  onNavigate: (index: number) => void;
}) {
  const { cards, index, title } = state;
  const currentCard = cards[index];
  const hasPrev = index > 0;
  const hasNext = index < cards.length - 1;

  const goToPrev = useCallback(() => {
    if (hasPrev) onNavigate(index - 1);
  }, [hasPrev, index, onNavigate]);

  const goToNext = useCallback(() => {
    if (hasNext) onNavigate(index + 1);
  }, [hasNext, index, onNavigate]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "ArrowLeft") {
        goToPrev();
      } else if (e.key === "ArrowRight") {
        goToNext();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [goToPrev, goToNext, onClose]);

  useEffect(() => {
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, []);

  const touchStartX = useRef<number | null>(null);
  const touchStartY = useRef<number | null>(null);

  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
    touchStartY.current = e.touches[0].clientY;
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStartX.current === null || touchStartY.current === null) return;
    const deltaX = e.changedTouches[0].clientX - touchStartX.current;
    const deltaY = e.changedTouches[0].clientY - touchStartY.current;
    touchStartX.current = null;
    touchStartY.current = null;

    if (Math.abs(deltaX) > 40 && Math.abs(deltaX) > Math.abs(deltaY) * 1.2) {
      if (deltaX < 0 && hasNext) {
        goToNext();
      } else if (deltaX > 0 && hasPrev) {
        goToPrev();
      }
    }
  };

  if (!currentCard) return null;

  return (
    <div
      className={styles.lightboxOverlay}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={currentCard.display_name || currentCard.name}
    >
      <div className={styles.lightboxStage} onClick={(e) => e.stopPropagation()}>
        {cards.length > 1 && (
          <button
            type="button"
            className={`${styles.lightboxNav} ${styles.lightboxPrev}`}
            onClick={goToPrev}
            disabled={!hasPrev}
            aria-label="Previous card"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
        )}

        <div
          className={styles.lightboxContainer}
          onTouchStart={handleTouchStart}
          onTouchEnd={handleTouchEnd}
        >
          <button
            type="button"
            className={styles.lightboxClose}
            onClick={onClose}
            aria-label="Close card view"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>

          <div className={styles.lightboxCardWrapper}>
            <div className={styles.lightboxImageWrapper}>
              {currentCard.image_url ? (
                <img
                  key={currentCard.name}
                  className={styles.lightboxImage}
                  src={currentCard.image_url}
                  alt={currentCard.display_name || currentCard.name}
                />
              ) : (
                <div className={styles.lightboxImagePlaceholder}>
                  <span>No image available</span>
                </div>
              )}
            </div>

            <div className={styles.lightboxDetails}>
              {title ? <p className={styles.lightboxTitle}>{title}</p> : null}
              <h3 className={styles.lightboxCardName}>{currentCard.display_name || currentCard.name}</h3>

              <div className={styles.lightboxMetaRow}>
                {currentCard.usd_price !== null && currentCard.usd_price !== undefined ? (
                  <div className={styles.lightboxPriceBadge}>
                    <span className={styles.lightboxPriceLabel}>Est. Price</span>
                    <span className={styles.lightboxPriceValue}>${currentCard.usd_price.toFixed(2)}</span>
                  </div>
                ) : (
                  <div className={styles.lightboxPriceBadge}>
                    <span className={styles.lightboxPriceLabel}>Est. Price</span>
                    <span className={styles.lightboxPriceMuted}>N/A</span>
                  </div>
                )}

                {cards.length > 1 && (
                  <span className={styles.lightboxCounter}>
                    {index + 1} of {cards.length}
                  </span>
                )}
              </div>

              <a
                className={styles.lightboxBuyButton}
                href={tcgplayerCardUrl(currentCard)}
                target="_blank"
                rel="noreferrer"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <circle cx="9" cy="21" r="1" />
                  <circle cx="20" cy="21" r="1" />
                  <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
                </svg>
                Buy this card on TCGplayer
              </a>

              {cards.length > 1 && (
                <div className={styles.lightboxMobileNav}>
                  <button
                    type="button"
                    className={styles.lightboxMobileNavBtn}
                    onClick={goToPrev}
                    disabled={!hasPrev}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6" /></svg>
                    Prev
                  </button>
                  <span className={styles.lightboxMobileCounter}>
                    {index + 1} / {cards.length}
                  </span>
                  <button
                    type="button"
                    className={styles.lightboxMobileNavBtn}
                    onClick={goToNext}
                    disabled={!hasNext}
                  >
                    Next
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6" /></svg>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {cards.length > 1 && (
          <button
            type="button"
            className={`${styles.lightboxNav} ${styles.lightboxNext}`}
            onClick={goToNext}
            disabled={!hasNext}
            aria-label="Next card"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
