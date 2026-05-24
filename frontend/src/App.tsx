import { useState } from "react";

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

  async function searchSemanticCards() {
    setLoading(true);
    setError("");

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

  return (
    <main className="page">
      <section className="hero">
        <h1>MTG Deck Lab</h1>
        <p>Search your local MTG card database with exact filters or semantic ideas.</p>
      </section>

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
          <button onClick={() => setSemanticQuery("cheap creatures that reward sacrificing other creatures")}>
            sacrifice payoffs
          </button>
          <button onClick={() => setSemanticQuery("cards that draw when creatures die")}>
            death draw
          </button>
          <button onClick={() => setSemanticQuery("spells that destroy all creatures")}>
            board wipes
          </button>
          <button onClick={() => setSemanticQuery("cards that make lots of creature tokens")}>
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
                Color identity: {card.color_identity?.join(", ") || "Colorless"}
              </span>
              {card.keywords && card.keywords.length > 0 && (
                <span>Keywords: {card.keywords.join(", ")}</span>
              )}
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}