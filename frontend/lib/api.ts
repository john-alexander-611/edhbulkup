const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";

export type CardPresentation = { name: string; display_name: string; image_url: string | null };
export type DecklistCard = CardPresentation & { quantity: number; owned_quantity: number; owned: boolean; card_type: string };
export type DeckMatch = { commander_name: string; identity: string; match_score: number; match_percentage: number; owned_count: number; deck_size: number; image_url: string | null };
export type SearchResults = { results: DeckMatch[]; total: number };
export type ReplacementGroup = {
  tag: string;
  missing_cards: string[];
  missing_card_details: CardPresentation[];
  replacements: string[];
  replacement_details: CardPresentation[];
};
export type DeckAnalysis = {
  commander_name: string; identity: string; match_score: number; match_percentage: number;
  owned_count: number; missing_count: number; missing_cards: string[];
  missing_card_details: CardPresentation[]; average_decklist: DecklistCard[]; missing_by_tag: Record<string, string[]>;
  replacements_by_tag: ReplacementGroup[]; owned_synergy_cards: string[];
  same_type_replacements: Record<string, string[]>; warnings: string[]; image_url: string | null;
};
export type SearchFilters = {
  name?: string;
  identity?: string;
  contains?: string;
  exclude?: string;
  exclude_commanders?: string[];
  exclude_face?: boolean;
  exclude_partners?: boolean;
  only_owned_commanders?: boolean;
  limit?: number;
  offset?: number;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail ?? "The API request failed.");
  return body as T;
}

export function uploadCollection(file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<{ owned_count: number }>(`/api/collection/upload`, { method: "POST", body: form });
}

export function clearCollection() {
  return request<{ status: string }>("/api/collection/clear", { method: "POST" });
}

export function searchCommanders(filters: SearchFilters) {
  const params = new URLSearchParams();
  const { exclude_commanders, ...rest } = filters;

  Object.entries(rest).forEach(([key, value]) => {
    if (value === undefined || value === null || value === false || value === "") return;
    params.set(key, String(value));
  });

  (exclude_commanders ?? []).forEach((name) => {
    if (name.trim()) params.append("exclude_commanders", name);
  });

  return request<SearchResults>(`/api/search?${params.toString()}`);
}

export function getCommanderAnalysis(name: string) {
  const canonicalName = decodeURIComponent(name);
  return request<DeckAnalysis>(`/api/commanders/${encodeURIComponent(canonicalName)}`);
}

export function getCommanderSuggestions(query: string) {
  const params = new URLSearchParams({ q: query });
  return request<{ suggestions: string[] }>(`/api/commanders/suggestions?${params.toString()}`);
}

export function buildCommanderRoute(name: string) {
  return `/commanders/${encodeURIComponent(decodeURIComponent(name))}`;
}
