"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getCommanderAnalysis, type CardPresentation, type DeckAnalysis, type DecklistCard } from "@/lib/api";
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

function scryfallCardUrl(cardName: string) {
  return `https://scryfall.com/search?q=${encodeURIComponent(cardName)}`;
}

export default function CommanderPage() {
  const params = useParams<{ commanderName?: string | string[] }>();
  const [analysis, setAnalysis] = useState<DeckAnalysis | null>(null);
  const [error, setError] = useState("");
  const [expandedSuggestionGroups, setExpandedSuggestionGroups] = useState<Record<string, boolean>>({});

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

  return <main className={styles.page}>
    <Link href="/">← Back to search</Link>
    <header className={styles.header}>
      {analysis.image_url ? <a href={scryfallCardUrl(analysis.commander_name)} target="_blank" rel="noreferrer"><img className={styles.commanderImage} src={analysis.image_url} alt={analysis.commander_name} /></a> : null}
      <div className={styles.headerText}>
        <p className={styles.eyebrow}>{analysis.identity} COMMANDER</p>
        <h1>{analysis.commander_name}</h1>
        <p>{analysis.match_percentage.toFixed(1)}% match · {analysis.owned_count} owned · {analysis.missing_count} missing</p>
      </div>
    </header>
    <section>
      <h2>Average decklist</h2>
      <div className={styles.decklist}>
        {decklistTypeOrder.map((type) => {
          const cards = groupDecklist(analysis.average_decklist ?? [], analysis.commander_name)[type];
          if (!cards?.length) return null;
          const total = cards.reduce((sum, card) => sum + card.quantity, 0);
          return <div className={styles.decklistGroup} key={type}>
            <h3>{formatTagLabel(type)} ({total})</h3>
            <ul>{cards.map((card) => <DecklistCard card={card} key={card.name} />)}</ul>
          </div>;
        })}
      </div>
    </section>
    <section><h2>Missing cards</h2><div className={styles.grid}>{analysis.missing_card_details.map((card) => <Card card={card} key={card.name} />)}</div></section>
    <section><h2>Replacement recommendations</h2>{analysis.replacements_by_tag.map((group) => {
      const isExpanded = expandedSuggestionGroups[group.tag];
      const visibleReplacements = isExpanded ? group.replacement_details : group.replacement_details.slice(0, 10);
      const hasMoreSuggestions = group.replacement_details.length > 10 && !isExpanded;

      return <article className={styles.group} key={group.tag}><h3>{formatTagLabel(group.tag)}</h3>
        <div className={styles.subsection}><h4>Missing Cards</h4>{group.missing_card_details?.length ? <div className={styles.grid}>{group.missing_card_details.map((card) => <Card card={card} key={`${group.tag}-${card.name}`} />)}</div> : <p>Missing: {group.missing_cards.join(", ") || "None"}</p>}</div>
        <div className={styles.subsection}><h4>Suggested Replacements</h4><div className={styles.grid}>{visibleReplacements.map((card) => <Card card={card} key={card.name} />)}</div>{hasMoreSuggestions ? <button className={styles.moreSuggestions} type="button" onClick={() => setExpandedSuggestionGroups((groups) => ({ ...groups, [group.tag]: true }))}>More suggestions</button> : null}</div>
      </article>;
    })}</section>
  </main>;
}

function Card({ card }: { card: CardPresentation }) {
  return <a className={styles.cardLink} href={scryfallCardUrl(card.name)} target="_blank" rel="noreferrer">
    <span>{card.display_name || card.name}</span>
    {card.image_url ? <img className={styles.cardPreview} src={card.image_url} alt="" /> : null}
  </a>;
}

function DecklistCard({ card }: { card: DecklistCard }) {
  return <li className={`${styles.decklistCard} ${card.owned ? "" : styles.missingCard}`}>
    <strong>{card.quantity}</strong>
    <a className={styles.decklistLink} href={scryfallCardUrl(card.name)} target="_blank" rel="noreferrer">
      <span>{card.display_name || card.name}</span>
      {card.image_url ? <img className={styles.cardPreview} src={card.image_url} alt="" /> : null}
    </a>
  </li>;
}
