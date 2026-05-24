import { useState } from "react";

type Card = {
  id: number;
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
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [color, setColor] = useState("");
  const [maxManaValue, setMaxManaValue] = useState("");
  const [cards, setCards] = useState<Card[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function searchCards() {
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

  return (
    <main className="page">
      <section className="hero">
        <h1>MTG Deck Lab</h1>
        <p>Search your local MTG card database.</p>
      </section>

      <section className="search-panel">
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

        <button onClick={searchCards} disabled={loading}>
          {loading ? "Searching..." : "Search cards"}
        </button>
      </section>

      {error && <p className="error">{error}</p>}

      <section className="results">
        {cards.map((card) => (
          <article key={card.id} className="card">
            <div className="card-header">
              <h2>{card.name}</h2>
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
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}