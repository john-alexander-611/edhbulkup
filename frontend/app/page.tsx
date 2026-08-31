"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState, useRef } from "react";
import { buildCommanderRoute, clearCollection, getCommanderSuggestions, searchCommanders, uploadCollection, type DeckMatch } from "@/lib/api";
import styles from "./page.module.css";

const colors = ["W", "U", "B", "R", "G", "C"];
const STORAGE_KEY = "edh-bulk-up-state-v1";

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
  excludeUnlimited: boolean;
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

function restoreFile(fileName: string | null, fileDataUrl: string | null): File | null {
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
  const [excludeUnlimited, setExcludeUnlimited] = useState(true);
  const [results, setResults] = useState<DeckMatch[]>([]);
  const [message, setMessage] = useState("Upload your collection CSV to begin.");
  const [loading, setLoading] = useState(false);
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
      setExcludeUnlimited(session.excludeUnlimited ?? false);
      setResults(session.results ?? []);
      setMessage(session.message ?? "Upload your collection CSV to begin.");

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
      excludeUnlimited,
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
  }, [file, identity, contains, exclude, commanderName, excludedCommanders, excludeFace, excludePartners, excludeUnlimited, results, message, hydrated]);

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
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Upload failed.");
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
      setMessage("Upload your collection CSV to begin.");
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
      setMessage("Upload your collection CSV before searching.");
      return;
    }

    setLoading(true);
    try {
      setResults(await searchCommanders({
        name: commanderName,
        identity: identity.join(""),
        contains: contains.join(""),
        exclude: exclude.join(""),
        exclude_commanders: excludedCommanders,
        exclude_face: excludeFace,
        exclude_partners: excludePartners,
        exclude_unlimited: excludeUnlimited,
        limit: 20,
      }));
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
        <p className={styles.eyebrow}>EDH BULK UP</p>
        <h1>Find the next deck in your collection</h1>
        <p className={styles.subtitle}>Upload your cards, filter commanders, and see exactly what is missing.</p>
      </header>
      <section className={styles.workspace}>
        <aside className={styles.controls}>
          <form onSubmit={handleUpload} className={styles.card}>
            <h2>Collection</h2>
            <input ref={fileInputRef} type="file" accept=".csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            <button type="submit" disabled={!file || loading}>Upload CSV</button>
            <button type="button" onClick={handleClearCollection} disabled={loading}>Clear Collection</button>
            <p className={styles.hint}>{message}</p>
          </form>
          <form onSubmit={handleSearch} className={styles.card}>
            <h2>Find commanders</h2>
            <label className={styles.field}>Search by name
              <div className={styles.commanderInputWrapper}>
                <input value={commanderName} onChange={(event) => handleCommanderNameChange(event.target.value)} onFocus={() => commanderName && setShowSuggestions(true)} onBlur={() => setTimeout(() => setShowSuggestions(false), 200)} placeholder="e.g., Atraxa, Myrkul" />
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
            <ColorGroup label="Exact identity" values={identity} colorType="identity" onColorChange={handleColorToggle} />
            <ColorGroup label="Contains all colors" values={contains} colorType="contains" onColorChange={handleColorToggle} />
            <ColorGroup label="Exclude colors" values={exclude} colorType="exclude" onColorChange={handleColorToggle} />
            <label className={styles.field}>Excluded commanders
              <div className={styles.commanderInputWrapper}>
                <input
                  value={excludeInput}
                  onChange={(event) => handleExcludeInputChange(event.target.value)}
                  onFocus={() => excludeInput && setShowExcludedSuggestions(true)}
                  onBlur={() => setTimeout(() => setShowExcludedSuggestions(false), 200)}
                   placeholder="e.g., Atraxa, Myrkul"
                />
                {showExcludedSuggestions && excludedSuggestions.length > 0 && (
                  <div className={styles.suggestions}>
                    {excludedSuggestions.map((name) => (
                      <div key={name} className={styles.suggestionItem} onClick={() => addExcludedCommander(name)}>
                        {name}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              {excludedCommanders.length > 0 && (
                <div className={styles.chipRow}>
                  {excludedCommanders.map((name) => (
                    <span key={name} className={styles.chip}>
                      {name}
                      <button
                        type="button"
                        className={styles.chipRemove}
                        onClick={() => removeExcludedCommander(name)}
                        aria-label={`Remove ${name}`}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </label>
            <label className={styles.field}>Advanced filters
              <div className={styles.colors}>
                <label><input type="checkbox" checked={excludeFace} onChange={() => setExcludeFace((value) => !value)} /> Exclude face</label>
                <label><input type="checkbox" checked={excludePartners} onChange={() => setExcludePartners((value) => !value)} /> Exclude partners</label>
                <label><input type="checkbox" checked={excludeUnlimited} onChange={() => setExcludeUnlimited((value) => !value)} /> Exclude unlimited</label>
              </div>
            </label>
            <button type="submit" disabled={loading || !file}>Search commanders</button>
          </form>
        </aside>
        <section className={styles.results}>
          <div className={styles.resultsHeader}><h2>Commander matches</h2><span>{results.length} results</span></div>
          {results.length === 0 ? <p className={styles.empty}>Your commander matches will appear here.</p> : results.map((result) => (
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
              </div>
              <div className={styles.resultMeta}><h3>{result.commander_name}</h3><p>{result.owned_count} of {result.deck_size} cards owned</p></div>
              <strong>{result.match_percentage.toFixed(1)}%</strong>
            </Link>
          ))}
        </section>
      </section>
    </main>
  );
}

function ColorGroup({ label, values, colorType, onColorChange }: { label: string; values: string[]; colorType?: 'identity' | 'contains' | 'exclude'; onColorChange?: (color: string, type: 'identity' | 'contains' | 'exclude') => void }) {
  const isIdentity = label === 'Exact identity';
  const displayColors = isIdentity ? colors : colors.filter((c) => c !== 'C');
  return <fieldset className={styles.colors}><legend>{label}</legend>{displayColors.map((color) => (
    <label key={color}><input type="checkbox" checked={values.includes(color)} onChange={() => onColorChange && colorType ? onColorChange(color, colorType) : undefined} />{color}</label>
  ))}</fieldset>;
}
