const AFFILIATE_BASE =
  process.env.NEXT_PUBLIC_TCGPLAYER_AFFILIATE_URL ??
  "https://partner.tcgplayer.com/c/7710003/1830156/21018";

function affiliateUrl(target: URL) {
  return `${AFFILIATE_BASE}?u=${encodeURIComponent(target.toString())}`;
}

/**
 * Affiliate link to a card on TCGplayer.
 *
 * Prefers the direct product page when a tcgplayer_id is available: the Impact
 * redirect appends its tracking params (irpid, irgwc, ...) to the target URL,
 * and on /search/magic/product TCGplayer renders those as extra junk filter
 * chips ("7710003", "1", the click id). Product pages ignore them, so they stay
 * clean. Falls back to a product search when there is no known product id.
 */
export function tcgplayerCardUrl(card: { name: string; display_name?: string; tcgplayer_id?: number | null }) {
  const id = card.tcgplayer_id;
  if (id) {
    const slug = (card.display_name || card.name).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    return affiliateUrl(new URL(`https://www.tcgplayer.com/product/${id}/magic-${slug}`));
  }
  const url = new URL("https://www.tcgplayer.com/search/magic/product");
  url.searchParams.set("productLineName", "magic");
  url.searchParams.set("q", card.name);
  return affiliateUrl(url);
}

/** Affiliate link to TCGplayer Mass Entry prefilled with the given cards. */
export function tcgplayerMassEntryUrl(cards: { name: string; quantity: number }[]) {
  const url = new URL("https://www.tcgplayer.com/massentry");
  url.searchParams.set("productline", "Magic");
  url.searchParams.set("c", cards.map((card) => `${card.quantity} ${card.name}`).join("||"));
  return affiliateUrl(url);
}
