"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useEffect, useState, useRef } from "react";
import { buildCommanderRoute, clearCollection, getCommanderSuggestions, searchCommanders, uploadCollection, type DeckMatch } from "@/lib/api";
import styles from "./page.module.css";
import { Analytics } from "@vercel/analytics/next"

const colors = ["W", "U", "B", "R", "G", "C"];
const colorNames: Record<string, string> = {
  W: "White",
  U: "Blue",
  B: "Black",
  R: "Red",
  G: "Green",
  C: "Colorless",
};
const STORAGE_KEY = "edh-bulk-up-state-v1";
const PAGE_SIZE = 20;

type SessionState = {
  fileName: string | null;
  fileDataUrl: string | null;
  identity: string[];
  contains: string[];
  exclude: string[];
  commanderName: string;
  excludedCommanders: string[];
  excludeFace: boolean;
  excludePartners: boolean;
  onlyOwnedCommanders: boolean;
  results: DeckMatch[];
  message: string;
};

function fileToDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(new Error("Unable to read uploaded file."));
    reader.readAsDataURL(file);
  });
}

function restoreFile(fileName: string | null, fileDataUrl: string | null): Promise<File | null> | null {
  if (!fileName || !fileDataUrl) return null;
  try {
    const response = fetch(fileDataUrl);
    return response.then((res) => res.blob()).then((blob) => new File([blob], fileName, { type: blob.type || "text/csv" }));
  } catch {
    return null;
  }
}

export default function HomePage() {
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [identity, setIdentity] = useState<string[]>([]);
  const [contains, setContains] = useState<string[]>([]);
  const [exclude, setExclude] = useState<string[]>([]);
  const [commanderName, setCommanderName] = useState("");
  const [excludedCommanders, setExcludedCommanders] = useState<string[]>([]);
  const [excludeInput, setExcludeInput] = useState("");
  const [excludeFace, setExcludeFace] = useState(true);
  const [excludePartners, setExcludePartners] = useState(true);
  const [onlyOwnedCommanders, setOnlyOwnedCommanders] = useState(true);
  const [results, setResults] = useState<DeckMatch[]>([]);
  const [message, setMessage] = useState("Upload your collection to begin (.csv exports from Moxfield/Archidekt, or .txt), or try our sample collection to see how it works!");
  const [loading, setLoading] = useState(false);
  const [totalResults, setTotalResults] = useState(0);
  const [page, setPage] = useState(1);
  const [hydrated, setHydrated] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const suggestionTimeout = useRef<NodeJS.Timeout | null>(null);
  const [excludedSuggestions, setExcludedSuggestions] = useState<string[]>([]);
  const [showExcludedSuggestions, setShowExcludedSuggestions] = useState(false);
  const excludedSuggestionTimeout = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      setHydrated(true);
      return;
    }

    try {
      const session: Partial<SessionState> = JSON.parse(stored) as Partial<SessionState>;
      setIdentity(session.identity ?? []);
      setContains(session.contains ?? []);
      setExclude(session.exclude ?? []);
      setCommanderName(session.commanderName ?? "");
      setExcludedCommanders(
        Array.isArray(session.excludedCommanders) ? session.excludedCommanders : []
      );
      setExcludeFace(session.excludeFace ?? true);
      setExcludePartners(session.excludePartners ?? true);
      setOnlyOwnedCommanders(session.onlyOwnedCommanders ?? true);
      setResults(Array.isArray(session.results) ? session.results : []);
      setMessage(session.message ?? "Upload your collection to begin. .csv exports from Moxfield and Archidekt are supported, as well as .txt files with quantity and cardname.");

      if (session.fileName && session.fileDataUrl) {
        void (async () => {
          const recovered = await restoreFile(session.fileName ?? null, session.fileDataUrl ?? null);
          if (recovered) {
            setFile(recovered);
            try {
              const response = await uploadCollection(recovered);
              setMessage(`${response.owned_count} unique cards loaded.`);
            } catch (error) {
              setMessage(error instanceof Error ? error.message : "Upload failed.");
            }
          }
        })();
      }
      setHydrated(true);
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
      setHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !hydrated) return;

    const payload: SessionState = {
      fileName: file?.name ?? null,
      fileDataUrl: file ? "" : null,
      identity,
      contains,
      exclude,
      commanderName,
      excludedCommanders,
      excludeFace,
      excludePartners,
      onlyOwnedCommanders,
      results,
      message,
    };

    void (async () => {
      if (!file) {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
        return;
      }

      try {
        payload.fileDataUrl = await fileToDataUrl(file);
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
      } catch {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...payload, fileDataUrl: null }));
      }
    })();
  }, [file, identity, contains, exclude, commanderName, excludedCommanders, excludeFace, excludePartners, onlyOwnedCommanders, results, message, hydrated]);

  const toggle = (values: string[], setValues: (next: string[]) => void, value: string) => {
    setValues(values.includes(value) ? values.filter((item) => item !== value) : [...values, value]);
  };

  function handleColorToggle(value: string, colorType: 'identity' | 'contains' | 'exclude') {
    if (colorType === 'identity') {
      if (value === 'C') {
        // Toggle C: if turning on, clear all other filters; if turning off, allow others
        if (!identity.includes('C')) {
          setIdentity(['C']);
          setContains([]);
          setExclude([]);
        } else {
          setIdentity([]);
        }
      } else {
        // Toggling non-C: clear C from identity, then toggle the color
        const newIdentity = identity.filter((c) => c !== 'C').includes(value)
          ? identity.filter((c) => c !== value)
          : [...identity.filter((c) => c !== 'C'), value];
        setIdentity(newIdentity);
      }
    } else if (colorType === 'contains') {
      // Toggling contains: clear C from identity
      const newContains = contains.includes(value)
        ? contains.filter((c) => c !== value)
        : [...contains, value];
      setContains(newContains);
      if (newContains.length > 0 && identity.includes('C')) {
        setIdentity([]);
      }
    } else if (colorType === 'exclude') {
      // Toggling exclude: clear C from identity
      const newExclude = exclude.includes(value)
        ? exclude.filter((c) => c !== value)
        : [...exclude, value];
      setExclude(newExclude);
      if (newExclude.length > 0 && identity.includes('C')) {
        setIdentity([]);
      }
    }
  }

  function handleCommanderNameChange(value: string) {
    setCommanderName(value);
    setShowSuggestions(true);
    if (suggestionTimeout.current) clearTimeout(suggestionTimeout.current);
    suggestionTimeout.current = setTimeout(() => {
      if (value.trim()) {
        void getCommanderSuggestions(value)
          .then((result) => setSuggestions(result.suggestions))
          .catch(() => setSuggestions([]));
      } else {
        setSuggestions([]);
      }
    }, 300);
  }

  function selectSuggestion(name: string) {
    setCommanderName(name);
    setShowSuggestions(false);
    setSuggestions([]);
  }

  function handleExcludeInputChange(value: string) {
    setExcludeInput(value);
    setShowExcludedSuggestions(true);
    if (excludedSuggestionTimeout.current) clearTimeout(excludedSuggestionTimeout.current);

    excludedSuggestionTimeout.current = setTimeout(() => {
      if (value.trim()) {
        void getCommanderSuggestions(value)
          .then((result) => {
            const alreadySelected = new Set(excludedCommanders.map((n) => n.toLowerCase()));
            setExcludedSuggestions(
              result.suggestions.filter((n) => !alreadySelected.has(n.toLowerCase()))
            );
          })
          .catch(() => setExcludedSuggestions([]));
      } else {
        setExcludedSuggestions([]);
      }
    }, 300);
  }

  function addExcludedCommander(name: string) {
    setExcludedCommanders((current) => (current.includes(name) ? current : [...current, name]));
    setExcludeInput("");
    setShowExcludedSuggestions(false);
    setExcludedSuggestions([]);
  }

  function removeExcludedCommander(name: string) {
    setExcludedCommanders((current) => current.filter((n) => n !== name));
  }

  async function handleUpload(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setLoading(true);
    try {
      const response = await uploadCollection(file);
      setMessage(`${response.owned_count} unique cards loaded.`);
      await fetchPage(1);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Upload failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleLoadSampleCollection() {
    setLoading(true);
    try {
      const res = await fetch("/sample_collection.csv");
      if (!res.ok) throw new Error("Could not load sample collection file.");
      const blob = await res.blob();
      const sampleFile = new File([blob], "sample_collection.csv", { type: "text/csv" });
      const response = await uploadCollection(sampleFile);
      setFile(sampleFile);
      setMessage(`${response.owned_count} unique cards loaded from sample collection.`);

      const { results: matches, total } = await searchCommanders({
        name: commanderName,
        identity: identity.join(""),
        contains: contains.join(""),
        exclude: exclude.join(""),
        exclude_commanders: excludedCommanders,
        exclude_face: excludeFace,
        exclude_partners: excludePartners,
        only_owned_commanders: onlyOwnedCommanders,
        limit: PAGE_SIZE,
        offset: 0,
      });
      if (!Array.isArray(matches) || typeof total !== "number") {
        throw new Error("The search API returned an invalid response.");
      }
      setResults(matches);
      setTotalResults(total);
      setPage(1);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to load sample collection.");
    } finally {
      setLoading(false);
    }
  }

  async function handleClearCollection() {
    setLoading(true);
    try {
      await clearCollection();
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setResults([]);
      setTotalResults(0);
      setPage(1);
      setCommanderName("");
      setSuggestions([]);
      setShowSuggestions(false);
      setMessage("Upload your collection to begin (.csv exports from Moxfield/Archidekt, or .txt), or try our sample collection to see how it works!");
      window.localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to clear collection.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setMessage("Upload your collection before searching. .csv exports from Moxfield and Archidekt are supported, as well as .txt files with quantity and cardname.");
      return;
    }
    await fetchPage(1);
  }

  async function fetchPage(targetPage: number) {
    if (!file) return;
    setLoading(true);
    try {
      const { results: matches, total } = await searchCommanders({
        name: commanderName,
        identity: identity.join(""),
        contains: contains.join(""),
        exclude: exclude.join(""),
        exclude_commanders: excludedCommanders,
        exclude_face: excludeFace,
        exclude_partners: excludePartners,
        only_owned_commanders: onlyOwnedCommanders,
        limit: PAGE_SIZE,
        offset: (targetPage - 1) * PAGE_SIZE,
      });
      if (!Array.isArray(matches) || typeof total !== "number") {
        throw new Error("The search API returned an invalid response.");
      }
      setResults(matches);
      setTotalResults(total);
      setPage(targetPage);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Search failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.shell}>
      <header className={styles.hero}>
        <div className={styles.brand}>
          <Image
            className={styles.logo}
            src="/edh_bulk_up_logo_v3.png"
            alt="EDH Bulk Up"
            width={360}
            height={180}
            priority
          />
          <p className={styles.brandText}>Impact-Site-Verification: 5b991144-b0ca-48eb-b0c7-eaae68c5544e</p>
        </div>
        <p className={styles.collectionStatus}>{file ? "Collection loaded" : "No collection loaded"}</p>
      </header>
      <section className={styles.workspace}>
        <aside className={styles.controls}>
          <form onSubmit={handleUpload} className={`${styles.card} ${styles.collectionCard}`}>
            <h2>Collection</h2>
            <input ref={fileInputRef} type="file" accept=".csv,.txt,text/plain" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            {file && <p className={styles.fileName}>Current File: {file.name}</p>}
            <div className={styles.collectionActions}>
              <button type="submit" disabled={!file || loading}>Upload Collection</button>
              <button type="button" className={styles.sampleCollection} onClick={handleLoadSampleCollection} disabled={loading}>
                {loading && !file ? "Loading Demo..." : "Try Sample Collection"}
              </button>
              {file && (
                <button type="button" className={styles.clearCollection} onClick={handleClearCollection} disabled={loading}>
                  Clear Collection
                </button>
              )}
            </div>
            <div className={styles.sampleDownloadRow}>
              <a href="/sample_collection.csv" download="sample_collection.csv" className={styles.sampleDownloadLink}>
                Download sample CSV
              </a>
            </div>
            <p className={styles.hint}>{message}</p>
          </form>
          <form onSubmit={handleSearch} className={`${styles.card} ${styles.filterCard}`}>
            <div className={styles.filterHeading}>
              <h2>Find commanders</h2>
            </div>
            <label className={`${styles.field} ${styles.searchField}`}>Search by name
              <div className={styles.commanderInputWrapper}>
                <input value={commanderName} onChange={(event) => handleCommanderNameChange(event.target.value)} onFocus={() => commanderName && setShowSuggestions(true)} onBlur={() => setTimeout(() => setShowSuggestions(false), 200)} placeholder="Search commanders, e.g. Atraxa" />
                {showSuggestions && suggestions.length > 0 && (
                  <div className={styles.suggestions}>
                    {suggestions.map((name) => (
                      <div key={name} className={styles.suggestionItem} onClick={() => selectSuggestion(name)}>
                        {name}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </label>
            <button className={styles.searchSubmit} type="submit" disabled={loading || !file}>Search commanders</button>
            <div className={styles.filterOptions}>
                <ColorGroup label="Exact Color Identity" values={identity} colorType="identity" onColorChange={handleColorToggle} />
                <ColorGroup label="Contains Colors" values={contains} colorType="contains" onColorChange={handleColorToggle} />
                <ColorGroup label="Exclude Colors" values={exclude} colorType="exclude" onColorChange={handleColorToggle} />
                <label className={styles.field}>Excluded commanders
                  <div className={styles.commanderInputWrapper}>
                    <input value={excludeInput} onChange={(event) => handleExcludeInputChange(event.target.value)} onFocus={() => excludeInput && setShowExcludedSuggestions(true)} onBlur={() => setTimeout(() => setShowExcludedSuggestions(false), 200)} placeholder="Search commanders to exclude" />
                    {showExcludedSuggestions && excludedSuggestions.length > 0 && (
                      <div className={styles.suggestions}>
                        {excludedSuggestions.map((name) => <div key={name} className={styles.suggestionItem} onClick={() => addExcludedCommander(name)}>{name}</div>)}
                      </div>
                    )}
                  </div>
                  {excludedCommanders.length > 0 && <div className={styles.chipRow}>
                    {excludedCommanders.map((name) => <span key={name} className={styles.chip}>{name}<button type="button" className={styles.chipRemove} onClick={() => removeExcludedCommander(name)} aria-label={`Remove ${name}`}>×</button></span>)}
                  </div>}
                </label>
                <label className={styles.field}>Advanced filters
                  <div className={styles.colors}>
                    <label title="Exclude the face commanders from precons"><input type="checkbox" checked={excludeFace} onChange={() => setExcludeFace((value) => !value)} /> Exclude Face Commanders</label>
                    <label title="Exclude commmanders with partner"><input type="checkbox" checked={excludePartners} onChange={() => setExcludePartners((value) => !value)} /> Exclude Partner Commanders</label>
                    <label title="Exclude any commanders you don't already own"><input type="checkbox" checked={onlyOwnedCommanders} onChange={() => setOnlyOwnedCommanders((value) => !value)} /> Only Owned Commanders</label>
                  </div>
                </label>
            </div>
          </form>
        </aside>
        <section className={styles.results}>
          <div className={styles.resultsHeader}><h2>Commander Matches</h2><span>{totalResults} results</span></div>
          {results.length === 0 ? (
            <div className={styles.empty}>
              <p>Your commander matches will appear here.</p>
              {!file && (
                <button type="button" className={styles.emptySampleBtn} onClick={handleLoadSampleCollection} disabled={loading}>
                  {loading ? "Loading Demo..." : "Load Sample Collection to See Demo Matches"}
                </button>
              )}
            </div>
          ) : results.map((result) => (
            <Link className={styles.result} href={buildCommanderRoute(result.commander_name)} key={result.commander_name}>
              <div className={styles.resultImageWrap}>
                {result.image_url ? (
                  <img
                    className={styles.resultImage}
                    src={result.image_url}
                    alt={result.commander_name}
                    onError={(event) => {
                      const target = event.currentTarget as HTMLImageElement;
                      target.style.display = "none";
                    }}
                  />
                ) : (
                  <div className={styles.resultFallback}>Card</div>
                )}
                {result.image_url ? <img className={styles.resultPreview} src={result.image_url} alt="" /> : null}
              </div>
              <div className={styles.resultMeta}><h3>{result.commander_name}</h3><p>{result.owned_count} of {result.deck_size} cards owned</p></div>
              <strong>{result.match_percentage.toFixed(1)}%</strong>
            </Link>
          ))}
          {totalResults > PAGE_SIZE && (
            <Pagination
              page={page}
              totalPages={Math.ceil(totalResults / PAGE_SIZE)}
              disabled={loading}
              onPageChange={fetchPage}
            />
          )}
        </section>
      </section>
    </main>
  );
}

function Pagination({ page, totalPages, disabled, onPageChange }: { page: number; totalPages: number; disabled: boolean; onPageChange: (page: number) => void }) {
  const pageNumbers: (number | "ellipsis")[] = [];
  for (let candidate = 1; candidate <= totalPages; candidate += 1) {
    const isEdge = candidate === 1 || candidate === totalPages;
    const isNearCurrent = Math.abs(candidate - page) <= 1;
    if (isEdge || isNearCurrent) {
      pageNumbers.push(candidate);
    } else if (pageNumbers[pageNumbers.length - 1] !== "ellipsis") {
      pageNumbers.push("ellipsis");
    }
  }

  return (
    <nav className={styles.pagination} aria-label="Result pages">
      <button type="button" onClick={() => onPageChange(page - 1)} disabled={disabled || page <= 1}>Prev</button>
      {pageNumbers.map((entry, index) =>
        entry === "ellipsis" ? (
          <span key={`ellipsis-${index}`} className={styles.paginationEllipsis}>…</span>
        ) : (
          <button
            type="button"
            key={entry}
            className={entry === page ? styles.paginationActive : undefined}
            onClick={() => onPageChange(entry)}
            disabled={disabled || entry === page}
          >
            {entry}
          </button>
        )
      )}
      <button type="button" onClick={() => onPageChange(page + 1)} disabled={disabled || page >= totalPages}>Next</button>
    </nav>
  );
}

function ColorGroup({ label, values, colorType, onColorChange }: { label: string; values: string[]; colorType?: 'identity' | 'contains' | 'exclude'; onColorChange?: (color: string, type: 'identity' | 'contains' | 'exclude') => void }) {
  const isIdentity = label === 'Exact Color Identity';
  const displayColors = isIdentity ? colors : colors.filter((c) => c !== 'C');
  return <fieldset className={styles.colors}><legend>{label}</legend>{displayColors.map((color) => (
    <label key={color} aria-label={color} title={colorNames[color] ?? color}><input type="checkbox" checked={values.includes(color)} onChange={() => onColorChange && colorType ? onColorChange(color, colorType) : undefined} /><img className={styles.manaSymbol} src={`/mana/${color}.svg`} alt={color} title={colorNames[color] ?? color} /></label>
  ))}</fieldset>;
}
