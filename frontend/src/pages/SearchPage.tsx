import type { DeckLabState } from "../hooks/useDeckLab";
import { SectionCard } from "../components/ui/SectionCard";

type SearchPageProps = {
  lab: DeckLabState;
};

export function SearchPage({ lab }: SearchPageProps) {
  return (
    <div className="page-grid page-grid-search">
      <section className="stack">
        <SectionCard title="Card search" subtitle="Exact or semantic card discovery">
          <div className="mode-toggle">
            <button
              className={lab.mode === "exact" ? "active" : ""}
              onClick={() => {
                lab.setMode("exact");
              }}
              type="button"
            >
              Exact search
            </button>

            <button
              className={lab.mode === "semantic" ? "active" : ""}
              onClick={() => {
                lab.setMode("semantic");
              }}
              type="button"
            >
              Semantic search
            </button>
          </div>

          <div className="search-grid">
            {lab.mode === "exact" && (
              <>
                <label className="field">
                  <span>Card name</span>
                  <input
                    value={lab.name}
                    onChange={(event) => lab.setName(event.target.value)}
                    placeholder="Lightning"
                  />
                </label>

                <label className="field">
                  <span>Oracle text</span>
                  <input
                    value={lab.text}
                    onChange={(event) => lab.setText(event.target.value)}
                    placeholder="draw a card"
                  />
                </label>
              </>
            )}

            {lab.mode === "semantic" && (
              <label className="field field-wide">
                <span>Describe what you want</span>
                <input
                  value={lab.semanticQuery}
                  onChange={(event) => lab.setSemanticQuery(event.target.value)}
                  placeholder="cheap creatures that reward sacrificing other creatures"
                />
              </label>
            )}

            <label className="field">
              <span>Color identity</span>
              <select value={lab.color} onChange={(event) => lab.setColor(event.target.value)}>
                <option value="">Any</option>
                <option value="W">White</option>
                <option value="U">Blue</option>
                <option value="B">Black</option>
                <option value="R">Red</option>
                <option value="G">Green</option>
              </select>
            </label>

            <label className="field">
              <span>Max mana value</span>
              <input
                value={lab.maxManaValue}
                onChange={(event) => lab.setMaxManaValue(event.target.value)}
                placeholder="3"
                type="number"
              />
            </label>

            <button onClick={lab.handleSearch} disabled={lab.loading} type="button">
              {lab.loading ? "Searching..." : "Search cards"}
            </button>
          </div>

          {lab.mode === "semantic" && (
            <div className="chip-row">
              <span>Try:</span>
              <button
                type="button"
                onClick={() => lab.setSemanticQuery("cheap creatures that reward sacrificing other creatures")}
              >
                sacrifice payoffs
              </button>
              <button type="button" onClick={() => lab.setSemanticQuery("cards that draw when creatures die")}>
                death draw
              </button>
              <button type="button" onClick={() => lab.setSemanticQuery("spells that destroy all creatures")}>
                board wipes
              </button>
              <button
                type="button"
                onClick={() => lab.setSemanticQuery("cards that make lots of creature tokens")}
              >
                token makers
              </button>
            </div>
          )}
        </SectionCard>

        <SectionCard title="Search results" subtitle={`${lab.cards.length} cards shown`}>
          <div className="results">
            {lab.cards.length === 0 && <p className="muted">No cards yet. Run a search to populate this list.</p>}

            {lab.cards.map((card) => (
              <article key={card.id} className="card-item">
                <div className="card-item-header">
                  <div>
                    <h3>{card.name}</h3>
                    {card.score !== undefined && (
                      <p className="score">Similarity score: {card.score.toFixed(3)}</p>
                    )}
                  </div>

                  <span>{card.mana_cost}</span>
                </div>

                <p className="type-line">{card.type_line}</p>
                {card.oracle_text && <p className="oracle-text">{card.oracle_text}</p>}

                <div className="metadata">
                  <span>MV: {card.mana_value ?? "-"}</span>
                  <span>Color identity: {card.color_identity?.join(", ") || "Colorless"}</span>
                  {card.keywords && card.keywords.length > 0 && <span>Keywords: {card.keywords.join(", ")}</span>}
                </div>

                <button className="secondary-button" onClick={() => lab.addCardToSelectedDeck(card.id)} type="button">
                  Add to selected deck
                </button>
              </article>
            ))}
          </div>
        </SectionCard>
      </section>

      <aside className="stack">
        <SectionCard title="Suggestions" subtitle="Context-aware card recommendations" defaultOpen={false}>
          <label className="field">
            <span>Goal</span>
            <textarea
              value={lab.suggestionGoal}
              onChange={(event) => lab.setSuggestionGoal(event.target.value)}
              placeholder="more cards that support this deck's main strategy"
            />
          </label>

          <label className="field">
            <span>Max mana value</span>
            <input
              value={lab.suggestionMaxManaValue}
              onChange={(event) => lab.setSuggestionMaxManaValue(event.target.value)}
              placeholder="4"
              type="number"
            />
          </label>

          <button className="primary-button" onClick={lab.loadDeckSuggestions} disabled={lab.suggestionsLoading} type="button">
            {lab.suggestionsLoading ? "Finding..." : "Get suggestions"}
          </button>

          <div className="suggestion-list compact">
            {lab.suggestions.map((suggestion) => (
              <article key={suggestion.card.id} className="suggestion-card">
                <div className="suggestion-header">
                  <strong>{suggestion.card.name}</strong>
                  <span>{suggestion.card.mana_cost}</span>
                </div>

                <p>{suggestion.reason}</p>

                <div className="metadata">
                  <span>Score: {suggestion.score.toFixed(3)}</span>
                  <span>MV: {suggestion.card.mana_value ?? "-"}</span>
                </div>

                <button className="secondary-button" onClick={() => lab.addCardToSelectedDeck(suggestion.card.id)} type="button">
                  Add suggestion
                </button>
              </article>
            ))}
          </div>
        </SectionCard>
      </aside>
    </div>
  );
}
