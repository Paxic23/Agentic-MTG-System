import type { DeckLabState } from "../hooks/useDeckLab";
import { SectionCard } from "../components/ui/SectionCard";

type InsightsPageProps = {
  lab: DeckLabState;
};

export function InsightsPage({ lab }: InsightsPageProps) {
  return (
    <div className="page-grid page-grid-insights">
      <section className="stack">
        <SectionCard
          title="Deck health"
          subtitle={lab.deckHealthLoading ? "Refreshing checks..." : "Rules and structural diagnostics"}
        >
          {!lab.selectedDeck && <p className="muted">Select a deck to see health insights.</p>}

          {lab.rulesCheck && (
            <div className={`rules-status ${lab.rulesCheck.is_valid ? "valid" : "invalid"}`}>
              <strong>{lab.rulesCheck.is_valid ? "Valid-ish" : "Needs attention"}</strong>
              <span>
                {lab.rulesCheck.format ?? "Unknown format"} • {lab.rulesCheck.total_cards} cards
              </span>
            </div>
          )}

          {lab.rulesCheck && lab.rulesCheck.issues.length > 0 && (
            <div className="health-list">
              {lab.rulesCheck.issues.map((issue, index) => (
                <div key={`${issue.code}-${index}`} className={`health-item ${issue.severity}`}>
                  <strong>{issue.severity}</strong>
                  <p>{issue.message}</p>
                </div>
              ))}
            </div>
          )}

          {lab.rulesCheck && lab.rulesCheck.issues.length === 0 && (
            <p className="muted">No rules issues detected.</p>
          )}

          {lab.deckDiagnosis && (
            <>
              <h3>Themes</h3>
              <div className="tag-list">
                {lab.deckDiagnosis.themes.length > 0 ? (
                  lab.deckDiagnosis.themes.map((theme) => <span key={theme}>{theme}</span>)
                ) : (
                  <span>No strong themes detected yet</span>
                )}
              </div>

              <h3>Findings</h3>
              <div className="health-list">
                {lab.deckDiagnosis.findings.map((finding, index) => (
                  <div key={`${finding.category}-${index}`} className={`health-item ${finding.severity}`}>
                    <strong>{finding.category}</strong>
                    <p>{finding.message}</p>

                    {finding.suggested_goal && (
                      <button className="small-action-button" onClick={() => lab.useSuggestedGoal(finding.suggested_goal)} type="button">
                        Use as suggestion goal
                      </button>
                    )}
                  </div>
                ))}
              </div>

              <h3>Role counts</h3>
              <div className="role-grid">
                {Object.entries(lab.deckDiagnosis.role_counts)
                  .sort(([, a], [, b]) => b - a)
                  .map(([role, count]) => (
                    <div key={role}>
                      <span>{role}</span>
                      <strong>{count}</strong>
                    </div>
                  ))}
              </div>
            </>
          )}
        </SectionCard>

        {lab.deckAnalysis && (
          <SectionCard title="Mana and composition" subtitle="Curve, types, and colors" defaultOpen={false}>
            <div className="analysis-grid">
              <div>
                <span>Total cards</span>
                <strong>{lab.deckAnalysis.summary.total_cards}</strong>
              </div>
              <div>
                <span>Lands</span>
                <strong>{lab.deckAnalysis.summary.land_cards}</strong>
              </div>
              <div>
                <span>Nonlands</span>
                <strong>{lab.deckAnalysis.summary.nonland_cards}</strong>
              </div>
              <div>
                <span>Avg. MV</span>
                <strong>{lab.deckAnalysis.summary.average_mana_value ?? "-"}</strong>
              </div>
            </div>

            <h3>Mana curve</h3>
            <div className="mini-bars">
              {Object.entries(lab.deckAnalysis.mana_curve).map(([bucket, count]) => (
                <div key={bucket} className="mini-bar-row">
                  <span>{bucket}</span>
                  <div>
                    <div style={{ width: `${Math.max(count * 18, 8)}px` }} />
                  </div>
                  <strong>{count}</strong>
                </div>
              ))}
            </div>

            <h3>Types</h3>
            <div className="tag-list">
              {Object.entries(lab.deckAnalysis.type_counts).map(([type, count]) => (
                <span key={type}>
                  {type}: {count}
                </span>
              ))}
            </div>

            <h3>Colors</h3>
            <div className="tag-list">
              {Object.entries(lab.deckAnalysis.color_identity_counts).map(([colorName, count]) => (
                <span key={colorName}>
                  {colorName}: {count}
                </span>
              ))}
              {Object.keys(lab.deckAnalysis.color_identity_counts).length === 0 && <span>Colorless / none</span>}
            </div>
          </SectionCard>
        )}
      </section>

      <aside className="stack">
        <SectionCard title="Deck coach" subtitle="Actionable tuning advice">
          <label className="field">
            <span>Coach goal</span>
            <textarea
              value={lab.coachGoal}
              onChange={(event) => lab.setCoachGoal(event.target.value)}
              placeholder="make this deck better at surviving board wipes"
            />
          </label>

          <label className="field">
            <span>Max mana value for suggestions</span>
            <input
              value={lab.coachMaxManaValue}
              onChange={(event) => lab.setCoachMaxManaValue(event.target.value)}
              placeholder="5"
              type="number"
            />
          </label>

          <button className="primary-button" onClick={lab.runDeckCoach} disabled={lab.coachLoading} type="button">
            {lab.coachLoading ? "Running coach..." : "Run deck coach"}
          </button>

          {lab.coachGoalUsed && (
            <div className="coach-goal-used">
              <strong>Goal used</strong>
              <p>{lab.coachGoalUsed}</p>
            </div>
          )}

          {lab.coachReport && (
            <div className="coach-report-box">
              <h3>Coach report</h3>
              <pre>{lab.coachReport}</pre>
            </div>
          )}

          {lab.coachSuggestions.length > 0 && (
            <div className="coach-suggestions">
              <h3>Coach suggestions</h3>
              <div className="suggestion-list">
                {lab.coachSuggestions.map((suggestion) => (
                  <article key={suggestion.card.id} className="suggestion-card">
                    <div className="suggestion-header">
                      <div>
                        <strong>{suggestion.card.name}</strong>
                        <p>{suggestion.card.type_line}</p>
                      </div>
                      <span>{suggestion.card.mana_cost}</span>
                    </div>

                    {suggestion.card.oracle_text && <p className="suggestion-text">{suggestion.card.oracle_text}</p>}

                    <div className="metadata">
                      <span>MV: {suggestion.card.mana_value ?? "-"}</span>
                      <span>Score: {suggestion.score !== undefined ? suggestion.score.toFixed(3) : "-"}</span>
                    </div>

                    <button className="secondary-button" onClick={() => lab.addCardToSelectedDeck(suggestion.card.id)} type="button">
                      Add coach suggestion
                    </button>
                  </article>
                ))}
              </div>
            </div>
          )}
        </SectionCard>
      </aside>
    </div>
  );
}
