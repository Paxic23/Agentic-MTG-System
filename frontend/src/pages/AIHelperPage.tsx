import type { DeckLabState } from "../hooks/useDeckLab";
import { CoachReport } from "../components/ui/CoachReport";
import { SectionCard } from "../components/ui/SectionCard";

type AIHelperPageProps = {
  lab: DeckLabState;
};

export function AIHelperPage({ lab }: AIHelperPageProps) {
  return (
    <div className="stack">
      <SectionCard title="AI Helper" subtitle="Open-ended deck coaching and recommendations">
        {!lab.selectedDeck && (
          <p className="muted">Select or create a deck first, then ask for coaching help.</p>
        )}

        <label className="field">
          <span>What should the helper focus on? (optional)</span>
          <textarea
            value={lab.coachGoal}
            onChange={(event) => lab.setCoachGoal(event.target.value)}
            placeholder="Example: Help me make this deck faster against aggressive pods"
          />
        </label>

        <label className="field">
          <span>Max mana value for suggested cards (optional)</span>
          <input
            value={lab.coachMaxManaValue}
            onChange={(event) => lab.setCoachMaxManaValue(event.target.value)}
            placeholder="5"
            type="number"
          />
        </label>

        <button className="primary-button" onClick={lab.runDeckCoach} disabled={lab.coachLoading} type="button">
          {lab.coachLoading ? "Thinking..." : "Ask AI helper"}
        </button>

        {lab.coachGoalUsed && (
          <div className="coach-goal-used">
            <strong>Focus used</strong>
            <p>{lab.coachGoalUsed}</p>
          </div>
        )}

        {!lab.coachGoalUsed && lab.coachReport && (
          <div className="coach-goal-used">
            <strong>Focus used</strong>
            <p>Open-ended deck review.</p>
          </div>
        )}

        {lab.coachReport && (
          <div className="coach-report-box">
            <h3>Coach report</h3>
            <CoachReport report={lab.coachReport} />
          </div>
        )}

        {lab.coachSuggestions.length > 0 && (
          <div className="coach-suggestions">
            <h3>Suggested cards</h3>
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
                    Add suggestion
                  </button>
                </article>
              ))}
            </div>
          </div>
        )}
      </SectionCard>
    </div>
  );
}
