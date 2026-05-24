import { useEffect, useState } from "react";

type Card = {
  id: number;
  score?: number;
  name: string;
  mana_cost: string | null;
  mana_value: number | null;
  type_line: string | null;
  oracle_text: string | null;
  colors: string[] | null;
  color_identity: string[] | null;
  keywords: string[] | null;
};

type Deck = {
  id: number;
  name: string;
  format: string | null;
  description: string | null;
  created_at: string;
};

type DeckDetail = Deck & {
  cards: {
    quantity: number;
    is_commander: boolean;
    card: Card;
  }[];
};

type DeckAnalysis = {
  deck: Deck;
  summary: {
    total_cards: number;
    nonland_cards: number;
    land_cards: number;
    average_mana_value: number | null;
  };
  mana_curve: Record<string, number>;
  type_counts: Record<string, number>;
  color_identity_counts: Record<string, number>;
};

type DeckSuggestion = {
  score: number;
  reason: string;
  card: Card;
};

type DeckSuggestionResponse = {
  query_used: string;
  deck_colors: string[];
  allowed_colors: string[] | null;
  suggestions: DeckSuggestion[];
};

type DeckImportResult = {
  deck_id: number;
  imported_count: number;
  unmatched_count: number;
  skipped_count: number;
  imported: {
    quantity: number;
    card: Card;
  }[];
  unmatched: {
    line: string;
    parsed_name: string;
    quantity: number;
  }[];
  skipped: string[];
};

type DeckExportResult = {
  deck: Deck;
  decklist: string;
};

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function App() {
  const [mode, setMode] = useState<"exact" | "semantic">("exact");

  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [color, setColor] = useState("");
  const [maxManaValue, setMaxManaValue] = useState("");
  const [semanticQuery, setSemanticQuery] = useState("");

  const [cards, setCards] = useState<Card[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [decks, setDecks] = useState<Deck[]>([]);
  const [selectedDeckId, setSelectedDeckId] = useState<string>("");
  const [selectedDeck, setSelectedDeck] = useState<DeckDetail | null>(null);
  const [deckAnalysis, setDeckAnalysis] = useState<DeckAnalysis | null>(null);

  const [newDeckName, setNewDeckName] = useState("");
  const [newDeckFormat, setNewDeckFormat] = useState("Commander");
  const [newDeckDescription, setNewDeckDescription] = useState("");
  const [suggestionGoal, setSuggestionGoal] = useState(
  "more cards that support this deck's main strategy"
  );
  const [suggestionMaxManaValue, setSuggestionMaxManaValue] = useState("");
  const [suggestions, setSuggestions] = useState<DeckSuggestion[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);

  const [importDecklistText, setImportDecklistText] = useState("");
  const [replaceExistingImport, setReplaceExistingImport] = useState(false);
  const [importResult, setImportResult] = useState<DeckImportResult | null>(null);
  const [exportedDecklist, setExportedDecklist] = useState("");
  const [decklistLoading, setDecklistLoading] = useState(false);

  const isCommanderDeck =
    selectedDeck?.format?.toLowerCase() === "commander";

  const commanderEntry =
    selectedDeck?.cards.find((entry) => entry.is_commander) ?? null;

  const selectedDeckTotalCards =
    deckAnalysis?.summary.total_cards ??
    selectedDeck?.cards.reduce((total, entry) => total + entry.quantity, 0) ??
    0;


  useEffect(() => {
    loadDecks();
  }, []);

  useEffect(() => {
    if (selectedDeckId) {
      loadSelectedDeck(Number(selectedDeckId));
      loadDeckAnalysis(Number(selectedDeckId));
    } else {
      setSelectedDeck(null);
      setDeckAnalysis(null);
    }
  }, [selectedDeckId]);

  async function loadDecks() {
    try {
      const response = await fetch(`${API_URL}/decks`);

      if (!response.ok) {
        throw new Error(`Could not load decks: ${response.status}`);
      }

      const data = await response.json();
      setDecks(data);

      if (!selectedDeckId && data.length > 0) {
        setSelectedDeckId(String(data[0].id));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load decks");
    }
  }

  async function loadSelectedDeck(deckId: number) {
    try {
      const response = await fetch(`${API_URL}/decks/${deckId}`);

      if (!response.ok) {
        throw new Error(`Could not load deck: ${response.status}`);
      }

      const data = await response.json();
      setSelectedDeck(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load deck");
    }
  }

  async function loadDeckAnalysis(deckId: number) {
    try {
      const response = await fetch(`${API_URL}/decks/${deckId}/analysis`);

      if (!response.ok) {
        throw new Error(`Could not load analysis: ${response.status}`);
      }

      const data = await response.json();
      setDeckAnalysis(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load analysis");
    }
  }

  async function createDeck() {
    if (!newDeckName.trim()) {
      setError("Deck name is required");
      return;
    }

    setError("");

    try {
      const response = await fetch(`${API_URL}/decks`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: newDeckName.trim(),
          format: newDeckFormat.trim() || null,
          description: newDeckDescription.trim() || null,
        }),
      });

      if (!response.ok) {
        throw new Error(`Could not create deck: ${response.status}`);
      }

      const createdDeck = await response.json();

      setNewDeckName("");
      setNewDeckDescription("");

      await loadDecks();
      setSelectedDeckId(String(createdDeck.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create deck");
    }
  }

  async function searchExactCards() {
    setLoading(true);
    setError("");

    const params = new URLSearchParams();

    if (name.trim()) params.set("name", name.trim());
    if (text.trim()) params.set("text", text.trim());
    if (color.trim()) params.set("color", color.trim());
    if (maxManaValue.trim()) params.set("max_mana_value", maxManaValue.trim());

    params.set("limit", "50");

    try {
      const response = await fetch(`${API_URL}/cards?${params.toString()}`);

      if (!response.ok) {
        throw new Error(`API request failed: ${response.status}`);
      }

      const data = await response.json();
      setCards(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function loadDeckSuggestions() {
    if (!selectedDeckId) {
      setError("Create or select a deck first");
      return;
    }

    setSuggestionsLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/decks/${selectedDeckId}/suggestions`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            goal: suggestionGoal.trim() || null,
            limit: 10,
            max_mana_value: suggestionMaxManaValue
              ? Number(suggestionMaxManaValue)
              : null,
          }),
        }
      );

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        throw new Error(
          errorBody?.detail ?? `Could not load suggestions: ${response.status}`
        );
      }

      const data: DeckSuggestionResponse = await response.json();
      setSuggestions(data.suggestions);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load suggestions"
      );
    } finally {
      setSuggestionsLoading(false);
    }
  }

  async function setCardAsCommander(cardId: number) {
    if (!selectedDeckId) {
      setError("Create or select a Commander deck first");
      return;
    }

    setError("");

    try {
      const response = await fetch(
        `${API_URL}/decks/${selectedDeckId}/cards/${cardId}/commander`,
        {
          method: "PATCH",
        }
      );

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        throw new Error(
          errorBody?.detail ?? `Could not set commander: ${response.status}`
        );
      }

      await loadSelectedDeck(Number(selectedDeckId));
      await loadDeckAnalysis(Number(selectedDeckId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not set commander");
    }
  }


  async function clearCommander() {
    if (!selectedDeckId) return;

    setError("");

    try {
      const response = await fetch(
        `${API_URL}/decks/${selectedDeckId}/commander`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        throw new Error(
          errorBody?.detail ?? `Could not clear commander: ${response.status}`
        );
      }

      await loadSelectedDeck(Number(selectedDeckId));
      await loadDeckAnalysis(Number(selectedDeckId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not clear commander");
    }
  }

  async function searchSemanticCards() {
    setLoading(true);
    setError("");

    if (!semanticQuery.trim()) {
      setError("Semantic search needs a description");
      setLoading(false);
      return;
    }

  

    try {
      const response = await fetch(`${API_URL}/cards/semantic-search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: semanticQuery,
          limit: 25,
          color: color || null,
          max_mana_value: maxManaValue ? Number(maxManaValue) : null,
        }),
      });

      if (!response.ok) {
        throw new Error(`API request failed: ${response.status}`);
      }

      const data = await response.json();
      setCards(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  function handleSearch() {
    if (mode === "exact") {
      searchExactCards();
    } else {
      searchSemanticCards();
    }
  }

  async function addCardToSelectedDeck(cardId: number) {
    if (!selectedDeckId) {
      setError("Create or select a deck first");
      return;
    }

    setError("");

    try {
      const response = await fetch(`${API_URL}/decks/${selectedDeckId}/cards`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          card_id: cardId,
          quantity: 1,
        }),
      });

      if (!response.ok) {
        throw new Error(`Could not add card: ${response.status}`);
      }

      await loadSelectedDeck(Number(selectedDeckId));
      await loadDeckAnalysis(Number(selectedDeckId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add card");
    }
  }

  async function removeCardFromSelectedDeck(cardId: number) {
    if (!selectedDeckId) return;

    setError("");

    try {
      const response = await fetch(
        `${API_URL}/decks/${selectedDeckId}/cards/${cardId}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        throw new Error(`Could not remove card: ${response.status}`);
      }

      await loadSelectedDeck(Number(selectedDeckId));
      await loadDeckAnalysis(Number(selectedDeckId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove card");
    }
  }

  async function importDecklist() {
    if (!selectedDeckId) {
      setError("Create or select a deck first");
      return;
    }

    if (!importDecklistText.trim()) {
      setError("Paste a decklist first");
      return;
    }

    setDecklistLoading(true);
    setError("");
    setImportResult(null);

    try {
      const response = await fetch(`${API_URL}/decks/${selectedDeckId}/import`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          decklist: importDecklistText,
          replace_existing: replaceExistingImport,
        }),
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        throw new Error(
          errorBody?.detail ?? `Could not import decklist: ${response.status}`
        );
      }

      const data: DeckImportResult = await response.json();

      setImportResult(data);

      await loadSelectedDeck(Number(selectedDeckId));
      await loadDeckAnalysis(Number(selectedDeckId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not import decklist");
    } finally {
      setDecklistLoading(false);
    }
  }


  async function exportDecklist() {
    if (!selectedDeckId) {
      setError("Create or select a deck first");
      return;
    }

    setDecklistLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_URL}/decks/${selectedDeckId}/export`);

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        throw new Error(
          errorBody?.detail ?? `Could not export decklist: ${response.status}`
        );
      }

      const data: DeckExportResult = await response.json();
      setExportedDecklist(data.decklist);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not export decklist");
    } finally {
      setDecklistLoading(false);
    }
  }


  async function copyExportedDecklist() {
    if (!exportedDecklist.trim()) {
      return;
    }

    await navigator.clipboard.writeText(exportedDecklist);
  }

  return (
    <main className="page">
      <section className="hero">
        <h1>MTG Deck Lab</h1>
        <p>Search cards, build decks, and analyze your deck shape.</p>
      </section>

      <section className="layout">
        <section className="main-column">
          <section className="mode-toggle">
            <button
              className={mode === "exact" ? "active" : ""}
              onClick={() => {
                setMode("exact");
                setCards([]);
              }}
            >
              Exact search
            </button>

            <button
              className={mode === "semantic" ? "active" : ""}
              onClick={() => {
                setMode("semantic");
                setCards([]);
              }}
            >
              Semantic search
            </button>
          </section>

          <section className="search-panel">
            {mode === "exact" && (
              <>
                <div className="field">
                  <label>Card name</label>
                  <input
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder="Lightning"
                  />
                </div>

                <div className="field">
                  <label>Oracle text</label>
                  <input
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    placeholder="draw a card"
                  />
                </div>
              </>
            )}

            {mode === "semantic" && (
              <div className="field wide">
                <label>Describe what you want</label>
                <input
                  value={semanticQuery}
                  onChange={(event) => setSemanticQuery(event.target.value)}
                  placeholder="cheap creatures that reward sacrificing other creatures"
                />
              </div>
            )}

            <div className="field">
              <label>Color identity</label>
              <select
                value={color}
                onChange={(event) => setColor(event.target.value)}
              >
                <option value="">Any</option>
                <option value="W">White</option>
                <option value="U">Blue</option>
                <option value="B">Black</option>
                <option value="R">Red</option>
                <option value="G">Green</option>
              </select>
            </div>

            <div className="field">
              <label>Max mana value</label>
              <input
                value={maxManaValue}
                onChange={(event) => setMaxManaValue(event.target.value)}
                placeholder="3"
                type="number"
              />
            </div>

            <button onClick={handleSearch} disabled={loading}>
              {loading ? "Searching..." : "Search cards"}
            </button>
          </section>

          {mode === "semantic" && (
            <section className="examples">
              <p>Try:</p>
              <button
                onClick={() =>
                  setSemanticQuery(
                    "cheap creatures that reward sacrificing other creatures"
                  )
                }
              >
                sacrifice payoffs
              </button>
              <button
                onClick={() =>
                  setSemanticQuery("cards that draw when creatures die")
                }
              >
                death draw
              </button>
              <button
                onClick={() =>
                  setSemanticQuery("spells that destroy all creatures")
                }
              >
                board wipes
              </button>
              <button
                onClick={() =>
                  setSemanticQuery("cards that make lots of creature tokens")
                }
              >
                token makers
              </button>
            </section>
          )}

          {error && <p className="error">{error}</p>}

          <section className="results">
            {cards.map((card) => (
              <article key={card.id} className="card">
                <div className="card-header">
                  <div>
                    <h2>{card.name}</h2>
                    {card.score !== undefined && (
                      <p className="score">
                        Similarity score: {card.score.toFixed(3)}
                      </p>
                    )}
                  </div>

                  <span>{card.mana_cost}</span>
                </div>

                <p className="type-line">{card.type_line}</p>

                {card.oracle_text && (
                  <p className="oracle-text">{card.oracle_text}</p>
                )}

                <div className="metadata">
                  <span>MV: {card.mana_value ?? "—"}</span>
                  <span>
                    Color identity:{" "}
                    {card.color_identity?.join(", ") || "Colorless"}
                  </span>
                  {card.keywords && card.keywords.length > 0 && (
                    <span>Keywords: {card.keywords.join(", ")}</span>
                  )}
                </div>

                <button
                  className="secondary-button"
                  onClick={() => addCardToSelectedDeck(card.id)}
                >
                  Add to selected deck
                </button>
              </article>
            ))}
          </section>
        </section>

        <aside className="deck-panel">
          <section className="panel-card">
            <h2>Create deck</h2>

            <div className="field">
              <label>Deck name</label>
              <input
                value={newDeckName}
                onChange={(event) => setNewDeckName(event.target.value)}
                placeholder="Aristocrats Test Deck"
              />
            </div>

            <div className="field">
              <label>Format</label>
              <select
                value={newDeckFormat}
                onChange={(event) => setNewDeckFormat(event.target.value)}
              >
                <option value="Commander">Commander</option>
                <option value="Modern">Modern</option>
                <option value="Pioneer">Pioneer</option>
                <option value="Standard">Standard</option>
                <option value="Legacy">Legacy</option>
                <option value="Casual">Casual</option>
              </select>
            </div>

            <div className="field">
              <label>Description</label>
              <input
                value={newDeckDescription}
                onChange={(event) =>
                  setNewDeckDescription(event.target.value)
                }
                placeholder="Testing sacrifice payoff ideas"
              />
            </div>

            <button className="primary-button" onClick={createDeck}>
              Create deck
            </button>
          </section>

          <section className="panel-card">
            <h2>Selected deck</h2>

            <div className="field">
              <label>Deck</label>
              <select
                value={selectedDeckId}
                onChange={(event) => setSelectedDeckId(event.target.value)}
              >
                <option value="">No deck selected</option>
                {decks.map((deck) => (
                  <option key={deck.id} value={deck.id}>
                    {deck.name}
                  </option>
                ))}
              </select>
            </div>

            {selectedDeck && (
              <>
                <div className="deck-title-row">
                  <div>
                    <h3>{selectedDeck.name}</h3>
                    <p>{selectedDeck.format ?? "No format"}</p>
                  </div>

                  <span>{selectedDeck.cards.length} unique</span>
                </div>

                {isCommanderDeck && (
                  <div
                    className={[
                      "commander-counter",
                      selectedDeckTotalCards === 100 && commanderEntry ? "complete" : "",
                      selectedDeckTotalCards > 100 ? "over" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    <div>
                      <strong>{selectedDeckTotalCards}/100</strong>
                      <span>Commander deck size</span>
                    </div>

                    <div>
                      <strong>{commanderEntry ? "1/1" : "0/1"}</strong>
                      <span>Commander selected</span>
                    </div>
                  </div>
                )}

                {isCommanderDeck && (
                  <div className="commander-slot">
                    <h3>Commander</h3>

                    {commanderEntry ? (
                      <div className="commander-card">
                        <strong>{commanderEntry.card.name}</strong>
                        <span>{commanderEntry.card.mana_cost}</span>
                        <p>{commanderEntry.card.type_line}</p>

                        <button onClick={clearCommander}>Clear commander</button>
                      </div>
                    ) : (
                      <p className="muted">
                        No commander selected. Add a legendary creature to the deck, then mark it
                        as commander.
                      </p>
                    )}
                  </div>
                )}

                <div className="deck-list">
                  {selectedDeck.cards.length === 0 && (
                    <p className="muted">No cards added yet.</p>
                  )}

                  {selectedDeck.cards.map((entry) => (
                    <div
                    key={entry.card.id}
                    className={`deck-card-row ${entry.is_commander ? "commander-highlight" : ""}`}
                    >
                      <div>
                        <strong>
                          {entry.quantity}x {entry.card.name}
                        </strong>
                        <p>{entry.card.type_line}</p>
                      </div>

                      <div className="deck-card-actions">
                        {isCommanderDeck && !entry.is_commander && (
                          <button onClick={() => setCardAsCommander(entry.card.id)}>
                            Set commander
                          </button>
                        )}

                        {entry.is_commander && (
                          <span className="commander-badge">Commander</span>
                        )}

                        <button
                          onClick={() => removeCardFromSelectedDeck(entry.card.id)}
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </section>

          {selectedDeck && (
            <section className="panel-card">
              <h2>Import / Export</h2>

              <div className="field">
                <label>Paste decklist</label>
                <textarea
                  value={importDecklistText}
                  onChange={(event) => setImportDecklistText(event.target.value)}
                  placeholder={`1 Blood Artist
          1 Viscera Seer
          1 Village Rites`}
                />
              </div>

              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={replaceExistingImport}
                  onChange={(event) => setReplaceExistingImport(event.target.checked)}
                />
                Replace existing deck cards
              </label>

              <div className="button-row">
                <button
                  className="primary-button"
                  onClick={importDecklist}
                  disabled={decklistLoading}
                >
                  {decklistLoading ? "Working..." : "Import decklist"}
                </button>

                <button
                  className="secondary-button no-margin"
                  onClick={exportDecklist}
                  disabled={decklistLoading}
                >
                  Export decklist
                </button>
              </div>

              {importResult && (
                <div className="import-summary">
                  <p>
                    Imported <strong>{importResult.imported_count}</strong> cards.
                    {" "}
                    Unmatched <strong>{importResult.unmatched_count}</strong>.
                  </p>

                  {importResult.unmatched.length > 0 && (
                    <>
                      <h3>Unmatched</h3>
                      <div className="unmatched-list">
                        {importResult.unmatched.map((item, index) => (
                          <div key={`${item.line}-${index}`}>
                            <strong>{item.parsed_name}</strong>
                            <span>{item.line}</span>
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              )}

              {exportedDecklist && (
                <div className="export-box">
                  <div className="export-header">
                    <h3>Exported decklist</h3>
                    <button onClick={copyExportedDecklist}>Copy</button>
                  </div>

                  <textarea readOnly value={exportedDecklist} />
                </div>
              )}
            </section>
          )}

          {deckAnalysis && (
            <section className="panel-card">
              <h2>Analysis</h2>

              <div className="analysis-grid">
                <div>
                  <span>Total cards</span>
                  <strong>{deckAnalysis.summary.total_cards}</strong>
                </div>
                <div>
                  <span>Lands</span>
                  <strong>{deckAnalysis.summary.land_cards}</strong>
                </div>
                <div>
                  <span>Nonlands</span>
                  <strong>{deckAnalysis.summary.nonland_cards}</strong>
                </div>
                <div>
                  <span>Avg. MV</span>
                  <strong>
                    {deckAnalysis.summary.average_mana_value ?? "—"}
                  </strong>
                </div>
              </div>

              <h3>Mana curve</h3>
              <div className="mini-bars">
                {Object.entries(deckAnalysis.mana_curve).map(
                  ([bucket, count]) => (
                    <div key={bucket} className="mini-bar-row">
                      <span>{bucket}</span>
                      <div>
                        <div
                          style={{
                            width: `${Math.max(count * 18, 8)}px`,
                          }}
                        />
                      </div>
                      <strong>{count}</strong>
                    </div>
                  )
                )}
              </div>

              <h3>Types</h3>
              <div className="tag-list">
                {Object.entries(deckAnalysis.type_counts).map(
                  ([type, count]) => (
                    <span key={type}>
                      {type}: {count}
                    </span>
                  )
                )}
              </div>

              <h3>Colors</h3>
              <div className="tag-list">
                {Object.entries(deckAnalysis.color_identity_counts).map(
                  ([colorName, count]) => (
                    <span key={colorName}>
                      {colorName}: {count}
                    </span>
                  )
                )}

                {Object.keys(deckAnalysis.color_identity_counts).length ===
                  0 && <span>Colorless / none</span>}
              </div>
            </section>
          )}
        </aside>
      </section>
    </main>
  );
}