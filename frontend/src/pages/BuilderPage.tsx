import type { DeckLabState } from "../hooks/useDeckLab";
import { SectionCard } from "../components/ui/SectionCard";

type BuilderPageProps = {
  lab: DeckLabState;
};

export function BuilderPage({ lab }: BuilderPageProps) {
  return (
    <div className="page-grid page-grid-builder">
      <section className="stack">
        <SectionCard title="Create deck" subtitle="Start a new deck in seconds">
          <div className="form-grid two">
            <label className="field">
              <span>Deck name</span>
              <input
                value={lab.newDeckName}
                onChange={(event) => lab.setNewDeckName(event.target.value)}
                placeholder="Aristocrats Test Deck"
              />
            </label>

            <label className="field">
              <span>Format</span>
              <select
                value={lab.newDeckFormat}
                onChange={(event) => lab.setNewDeckFormat(event.target.value)}
              >
                <option value="Commander">Commander</option>
                <option value="Modern">Modern</option>
                <option value="Pioneer">Pioneer</option>
                <option value="Standard">Standard</option>
                <option value="Legacy">Legacy</option>
                <option value="Casual">Casual</option>
              </select>
            </label>
          </div>

          <label className="field">
            <span>Description</span>
            <input
              value={lab.newDeckDescription}
              onChange={(event) => lab.setNewDeckDescription(event.target.value)}
              placeholder="Testing sacrifice payoff ideas"
            />
          </label>

          <button className="primary-button" onClick={lab.createDeck} type="button">
            Create deck
          </button>
        </SectionCard>

        <SectionCard
          title={lab.selectedDeck?.name ?? "Selected deck"}
          subtitle={lab.selectedDeck?.format ?? "No deck selected"}
        >
          {!lab.selectedDeck && <p className="muted">Create or select a deck to begin building.</p>}

          {lab.selectedDeck && (
            <>
              <div className="deck-summary-strip">
                <div>
                  <span>Total cards</span>
                  <strong>{lab.selectedDeckTotalCards}</strong>
                </div>
                <div>
                  <span>Unique cards</span>
                  <strong>{lab.selectedDeck.cards.length}</strong>
                </div>
                <div>
                  <span>Format</span>
                  <strong>{lab.selectedDeck.format ?? "Unknown"}</strong>
                </div>
              </div>

              {lab.isCommanderDeck && (
                <div
                  className={[
                    "commander-counter",
                    lab.selectedDeckTotalCards === 100 && lab.commanderEntry ? "complete" : "",
                    lab.selectedDeckTotalCards > 100 ? "over" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <div>
                    <strong>{lab.selectedDeckTotalCards}/100</strong>
                    <span>Commander size</span>
                  </div>
                  <div>
                    <strong>{lab.commanderEntry ? "1/1" : "0/1"}</strong>
                    <span>Commander selected</span>
                  </div>
                </div>
              )}

              {lab.isCommanderDeck && (
                <div className="commander-slot">
                  <h3>Commander</h3>
                  {lab.commanderEntry ? (
                    <div className="commander-card">
                      <strong>{lab.commanderEntry.card.name}</strong>
                      <span>{lab.commanderEntry.card.mana_cost}</span>
                      <p>{lab.commanderEntry.card.type_line}</p>
                      <button onClick={lab.clearCommander} type="button">
                        Clear commander
                      </button>
                    </div>
                  ) : (
                    <p className="muted">Set one legendary creature as commander to satisfy format checks.</p>
                  )}
                </div>
              )}

              <div className="deck-list">
                {lab.selectedDeck.cards.length === 0 && <p className="muted">No cards added yet.</p>}
                {lab.selectedDeck.cards.map((entry) => (
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
                      {lab.isCommanderDeck && !entry.is_commander && (
                        <button onClick={() => lab.setCardAsCommander(entry.card.id)} type="button">
                          Set commander
                        </button>
                      )}

                      {entry.is_commander && <span className="commander-badge">Commander</span>}

                      <button onClick={() => lab.removeCardFromSelectedDeck(entry.card.id)} type="button">
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </SectionCard>
      </section>

      <aside className="stack">
        <SectionCard title="Import / Export" subtitle="Decklist workflow" defaultOpen={false}>
          <label className="field">
            <span>Paste decklist</span>
            <textarea
              value={lab.importDecklistText}
              onChange={(event) => lab.setImportDecklistText(event.target.value)}
              placeholder={`1 Blood Artist\n1 Viscera Seer\n1 Village Rites`}
            />
          </label>

          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={lab.replaceExistingImport}
              onChange={(event) => lab.setReplaceExistingImport(event.target.checked)}
            />
            Replace existing deck cards
          </label>

          <div className="button-row">
            <button className="primary-button" onClick={lab.importDecklist} disabled={lab.decklistLoading} type="button">
              {lab.decklistLoading ? "Working..." : "Import decklist"}
            </button>

            <button className="secondary-button no-margin" onClick={lab.exportDecklist} disabled={lab.decklistLoading} type="button">
              Export decklist
            </button>
          </div>

          {lab.importResult && (
            <div className="import-summary">
              <p>
                Imported <strong>{lab.importResult.imported_count}</strong> cards. Unmatched{" "}
                <strong>{lab.importResult.unmatched_count}</strong>.
              </p>

              {lab.importResult.unmatched.length > 0 && (
                <div className="unmatched-list">
                  {lab.importResult.unmatched.map((item, index) => (
                    <div key={`${item.line}-${index}`}>
                      <strong>{item.parsed_name}</strong>
                      <span>{item.line}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {lab.exportedDecklist && (
            <div className="export-box">
              <div className="export-header">
                <h3>Exported decklist</h3>
                <button onClick={lab.copyExportedDecklist} type="button">
                  Copy
                </button>
              </div>

              <textarea readOnly value={lab.exportedDecklist} />
            </div>
          )}
        </SectionCard>
      </aside>
    </div>
  );
}
