import { CARD_TYPES, type DeckLabState } from "../hooks/useDeckLab";
import { CardTable } from "../components/ui/CardTable";
import { SectionCard } from "../components/ui/SectionCard";

type SearchPageProps = {
  lab: DeckLabState;
};

export function SearchPage({ lab }: SearchPageProps) {
  return (
    <div className="page-grid page-grid-search">
      <section className="stack">
        <SectionCard
          title="Search"
          actions={
            <div className="mode-toggle">
              <button
                className={lab.mode === "exact" ? "active" : ""}
                onClick={() => {
                  lab.setMode("exact");
                }}
                type="button"
              >
                Exact
              </button>

              <button
                className={lab.mode === "semantic" ? "active" : ""}
                onClick={() => {
                  lab.setMode("semantic");
                }}
                type="button"
              >
                Semantic
              </button>
            </div>
          }
        >
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
              {lab.loading ? "Searching…" : "Search"}
            </button>
          </div>

          {lab.mode === "semantic" && (
            <div className="type-filter">
              <div className="type-filter-header">
                <span>Card types</span>
                <small className="muted">Click once to include, twice to exclude, again to reset.</small>
                {Object.keys(lab.typeFilters).length > 0 && (
                  <button type="button" className="type-filter-clear" onClick={() => lab.setTypeFilters({})}>
                    Clear
                  </button>
                )}
              </div>
              <div className="ignore-chip-grid">
                {CARD_TYPES.map((cardType) => {
                  const state = lab.typeFilters[cardType];
                  return (
                    <button
                      key={cardType}
                      type="button"
                      className={`ignore-chip type-chip ${state === "include" ? "active" : ""} ${
                        state === "exclude" ? "excluded" : ""
                      }`}
                      aria-pressed={Boolean(state)}
                      title={state ? `${cardType}: ${state}d` : `${cardType}: any`}
                      onClick={() => lab.cycleTypeFilter(cardType)}
                    >
                      {state === "include" ? "+ " : state === "exclude" ? "− " : ""}
                      {cardType}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

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

        <SectionCard title="Results" subtitle={lab.cards.length > 0 ? `${lab.cards.length} cards` : undefined}>
          <CardTable
            showScore={lab.cards.some((card) => card.score !== undefined)}
            empty={<p className="muted">Nothing here yet. Try a card name, or switch to semantic and describe what you need.</p>}
            rows={lab.cards.map((card) => ({
              key: card.id,
              card,
              score: card.score,
              rowActions: (
                <button className="icon-button" onClick={() => lab.addCardToSelectedDeck(card.id)} type="button" title="Add to deck" aria-label={`Add ${card.name} to deck`}>
                  +
                </button>
              ),
              detailActions: (
                <>
                  <button className="primary-button" onClick={() => lab.addCardToSelectedDeck(card.id)} type="button">
                    {lab.selectedDeck ? `Add to ${lab.selectedDeck.name}` : "Add to deck"}
                  </button>
                  <button className="text-link" onClick={() => lab.findSimilarCards(card)} type="button">
                    Find similar
                  </button>
                </>
              ),
            }))}
          />
        </SectionCard>
      </section>

      <aside className="stack">
        <SectionCard title="Ideas for this deck" defaultOpen={false}>
          <label className="field">
            <span>Goal (optional)</span>
            <textarea
              value={lab.suggestionGoal}
              onChange={(event) => lab.setSuggestionGoal(event.target.value)}
              placeholder="protection for a creature-heavy strategy"
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
            {lab.suggestionsLoading ? "Looking…" : "Suggest cards"}
          </button>

          {lab.suggestions.length > 0 && (
            <div className="suggestion-list">
              <CardTable
                showType={false}
                rows={lab.suggestions.map((suggestion) => ({
                  key: suggestion.card.id,
                  card: suggestion.card,
                  note: suggestion.reason,
                  rowActions: (
                    <button className="icon-button" onClick={() => lab.addCardToSelectedDeck(suggestion.card.id)} type="button" title="Add to deck" aria-label={`Add ${suggestion.card.name} to deck`}>
                      +
                    </button>
                  ),
                  detailActions: (
                    <button className="text-link" onClick={() => lab.findSimilarCards(suggestion.card)} type="button">
                      Find similar
                    </button>
                  ),
                }))}
              />
            </div>
          )}
        </SectionCard>
      </aside>
    </div>
  );
}
