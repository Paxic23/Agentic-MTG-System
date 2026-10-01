import { useNavigate } from "react-router-dom";
import type { DeckLabState } from "../hooks/useDeckLab";
import { CardTable } from "../components/ui/CardTable";
import { CoachReport } from "../components/ui/CoachReport";
import { SectionCard } from "../components/ui/SectionCard";

type AIHelperPageProps = {
  lab: DeckLabState;
};

export function AIHelperPage({ lab }: AIHelperPageProps) {
  const navigate = useNavigate();

  const helperIgnoreOptions = Array.from(
    new Set([
      "ramp",
      "card draw",
      "interaction",
      "board wipes",
      "mana base",
      "mana curve",
      "deck size",
      "commander",
      ...(lab.deckDiagnosis?.findings.map((finding) => finding.category) ?? []),
    ]),
  ).sort((left, right) => left.localeCompare(right));

  function toggleIgnoredCategory(category: string) {
    const normalized = category.trim().toLowerCase();
    if (!normalized) {
      return;
    }

    if (lab.coachIgnoredCategories.includes(normalized)) {
      lab.setCoachIgnoredCategories(
        lab.coachIgnoredCategories.filter((current) => current !== normalized),
      );
      return;
    }

    lab.setCoachIgnoredCategories([...lab.coachIgnoredCategories, normalized]);
  }

  return (
    <div className="stack">
      <SectionCard title="Deck coach" subtitle={lab.selectedDeck?.name}>
        {!lab.selectedDeck && (
          <p className="muted">Pick a deck in the top bar first.</p>
        )}

        <label className="field">
          <span>What should the coach focus on? (optional)</span>
          <textarea
            value={lab.coachGoal}
            onChange={(event) => lab.setCoachGoal(event.target.value)}
            placeholder="Make this deck faster against aggressive pods"
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

        <div className="field">
          <span>Skip advice about (optional)</span>
          <div className="ignore-chip-grid">
            {helperIgnoreOptions.map((category) => {
              const normalized = category.trim().toLowerCase();
              const isActive = lab.coachIgnoredCategories.includes(normalized);

              return (
                <button
                  key={category}
                  type="button"
                  className={`ignore-chip ${isActive ? "active" : ""}`}
                  onClick={() => toggleIgnoredCategory(category)}
                >
                  {category}
                </button>
              );
            })}
          </div>
        </div>

        <button className="primary-button" onClick={lab.runDeckCoach} disabled={lab.coachLoading} type="button">
          {lab.coachLoading ? "Thinking…" : "Review my deck"}
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
            <CardTable
              showScore
              rows={lab.coachSuggestions.map((suggestion) => ({
                key: suggestion.card.id,
                card: suggestion.card,
                score: suggestion.score,
                rowActions: (
                  <button className="icon-button" onClick={() => lab.addCardToSelectedDeck(suggestion.card.id)} type="button" title="Add to deck" aria-label={`Add ${suggestion.card.name} to deck`}>
                    +
                  </button>
                ),
                detailActions: (
                  <>
                    <button className="primary-button" onClick={() => lab.addCardToSelectedDeck(suggestion.card.id)} type="button">
                      Add to deck
                    </button>
                    <button
                      className="text-link"
                      onClick={() => {
                        lab.findSimilarCards(suggestion.card);
                        navigate("/search");
                      }}
                      type="button"
                    >
                      Find similar
                    </button>
                  </>
                ),
              }))}
            />
          </div>
        )}
      </SectionCard>
    </div>
  );
}
