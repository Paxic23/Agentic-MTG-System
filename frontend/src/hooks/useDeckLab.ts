import { useEffect, useMemo, useState } from "react";
import {
  addCardToDeck,
  clearDeckCommander,
  createDeck as createDeckApi,
  exportDecklist as exportDecklistApi,
  fetchDeck,
  fetchDeckAnalysis,
  fetchDeckDiagnosis,
  fetchDeckRulesCheck,
  fetchDeckSuggestions,
  fetchDecks,
  importDecklist as importDecklistApi,
  removeCardFromDeck,
  runDeckCoach as runDeckCoachApi,
  searchCards,
  semanticSearchCards,
  setDeckCommander,
} from "../api";
import type {
  Card,
  Deck,
  DeckAnalysis,
  DeckDetail,
  DeckDiagnosis,
  DeckImportResult,
  DeckSuggestion,
  RulesCheck,
} from "../types";

export type SearchMode = "exact" | "semantic";

export function useDeckLab() {
  const [mode, setMode] = useState<SearchMode>("exact");

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

  const [suggestionGoal, setSuggestionGoal] = useState("");
  const [suggestionMaxManaValue, setSuggestionMaxManaValue] = useState("");
  const [suggestions, setSuggestions] = useState<DeckSuggestion[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);

  const [importDecklistText, setImportDecklistText] = useState("");
  const [replaceExistingImport, setReplaceExistingImport] = useState(false);
  const [importResult, setImportResult] = useState<DeckImportResult | null>(null);
  const [exportedDecklist, setExportedDecklist] = useState("");
  const [decklistLoading, setDecklistLoading] = useState(false);

  const [rulesCheck, setRulesCheck] = useState<RulesCheck | null>(null);
  const [deckDiagnosis, setDeckDiagnosis] = useState<DeckDiagnosis | null>(null);
  const [deckHealthLoading, setDeckHealthLoading] = useState(false);

  const [coachGoal, setCoachGoal] = useState("");
  const [coachMaxManaValue, setCoachMaxManaValue] = useState("");
  const [coachReport, setCoachReport] = useState("");
  const [coachGoalUsed, setCoachGoalUsed] = useState("");
  const [coachSuggestions, setCoachSuggestions] = useState<DeckSuggestion[]>([]);
  const [coachLoading, setCoachLoading] = useState(false);

  const isCommanderDeck = selectedDeck?.format?.toLowerCase() === "commander";

  const commanderEntry = selectedDeck?.cards.find((entry) => entry.is_commander) ?? null;

  const selectedDeckTotalCards =
    deckAnalysis?.summary.total_cards ??
    selectedDeck?.cards.reduce((total, entry) => total + entry.quantity, 0) ??
    0;

  useEffect(() => {
    void loadDecks();
    // Load deck options once.
  }, []);

  useEffect(() => {
    if (!selectedDeckId) {
      setSelectedDeck(null);
      setDeckAnalysis(null);
      setRulesCheck(null);
      setDeckDiagnosis(null);
      return;
    }

    const deckId = Number(selectedDeckId);
    void Promise.all([loadSelectedDeck(deckId), loadDeckAnalysis(deckId), loadDeckHealth(deckId)]);
  }, [selectedDeckId]);

  async function loadDecks() {
    try {
      const data = await fetchDecks();
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
      const data = await fetchDeck(deckId);
      setSelectedDeck(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load deck");
    }
  }

  async function loadDeckAnalysis(deckId: number) {
    try {
      const data = await fetchDeckAnalysis(deckId);
      setDeckAnalysis(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load analysis");
    }
  }

  async function loadDeckHealth(deckId: number) {
    setDeckHealthLoading(true);

    try {
      const [rulesData, diagnosisData] = await Promise.all([
        fetchDeckRulesCheck(deckId),
        fetchDeckDiagnosis(deckId),
      ]);

      setRulesCheck(rulesData);
      setDeckDiagnosis(diagnosisData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load deck health");
    } finally {
      setDeckHealthLoading(false);
    }
  }

  async function createDeck() {
    if (!newDeckName.trim()) {
      setError("Deck name is required");
      return;
    }

    setError("");

    try {
      const createdDeck = await createDeckApi({
        name: newDeckName.trim(),
        format: newDeckFormat.trim() || null,
        description: newDeckDescription.trim() || null,
      });

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

    try {
      const data = await searchCards({
        name,
        text,
        color,
        maxManaValue,
        limit: 50,
      });

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

    if (!semanticQuery.trim()) {
      setError("Semantic search needs a description");
      setLoading(false);
      return;
    }

    try {
      const data = await semanticSearchCards({
        query: semanticQuery,
        color,
        maxManaValue,
        limit: 25,
      });

      setCards(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  function handleSearch() {
    if (mode === "exact") {
      void searchExactCards();
      return;
    }

    void searchSemanticCards();
  }

  async function loadDeckSuggestions() {
    if (!selectedDeckId) {
      setError("Create or select a deck first");
      return;
    }

    setSuggestionsLoading(true);
    setError("");

    try {
      const data = await fetchDeckSuggestions({
        deckId: selectedDeckId,
        goal: suggestionGoal,
        maxManaValue: suggestionMaxManaValue,
        limit: 10,
      });

      setSuggestions(data.suggestions);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load suggestions");
    } finally {
      setSuggestionsLoading(false);
    }
  }

  async function addCardToSelectedDeck(cardId: number) {
    if (!selectedDeckId) {
      setError("Create or select a deck first");
      return;
    }

    setError("");

    try {
      await addCardToDeck({
        deckId: selectedDeckId,
        cardId,
        quantity: 1,
      });

      const deckId = Number(selectedDeckId);
      await Promise.all([loadSelectedDeck(deckId), loadDeckAnalysis(deckId), loadDeckHealth(deckId)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add card");
    }
  }

  async function removeCardFromSelectedDeck(cardId: number) {
    if (!selectedDeckId) {
      return;
    }

    setError("");

    try {
      await removeCardFromDeck({ deckId: selectedDeckId, cardId });

      const deckId = Number(selectedDeckId);
      await Promise.all([loadSelectedDeck(deckId), loadDeckAnalysis(deckId), loadDeckHealth(deckId)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove card");
    }
  }

  async function setCardAsCommander(cardId: number) {
    if (!selectedDeckId) {
      setError("Create or select a Commander deck first");
      return;
    }

    setError("");

    try {
      await setDeckCommander({ deckId: selectedDeckId, cardId });

      const deckId = Number(selectedDeckId);
      await Promise.all([loadSelectedDeck(deckId), loadDeckAnalysis(deckId), loadDeckHealth(deckId)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not set commander");
    }
  }

  async function clearCommander() {
    if (!selectedDeckId) {
      return;
    }

    setError("");

    try {
      await clearDeckCommander(selectedDeckId);

      const deckId = Number(selectedDeckId);
      await Promise.all([loadSelectedDeck(deckId), loadDeckAnalysis(deckId), loadDeckHealth(deckId)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not clear commander");
    }
  }

  async function importDecklist() {
    if (!importDecklistText.trim()) {
      setError("Paste a decklist first");
      return;
    }

    setDecklistLoading(true);
    setError("");
    setImportResult(null);

    try {
      let targetDeckId = selectedDeckId;

      if (!targetDeckId) {
        if (!newDeckName.trim()) {
          setError("Select a deck, or provide a deck name to create one during import");
          return;
        }

        const createdDeck = await createDeckApi({
          name: newDeckName.trim(),
          format: newDeckFormat.trim() || null,
          description: newDeckDescription.trim() || null,
        });

        targetDeckId = String(createdDeck.id);
        setSelectedDeckId(targetDeckId);
        setNewDeckName("");
        setNewDeckDescription("");
        await loadDecks();
      }

      const data = await importDecklistApi({
        deckId: targetDeckId,
        decklist: importDecklistText,
        replaceExisting: replaceExistingImport,
      });

      setImportResult(data);

      const deckId = Number(targetDeckId);
      await Promise.all([loadSelectedDeck(deckId), loadDeckAnalysis(deckId), loadDeckHealth(deckId)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not import decklist");
    } finally {
      setDecklistLoading(false);
    }
  }

  async function createDeckFromImport() {
    if (!newDeckName.trim()) {
      setError("Deck name is required to create a deck from import");
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
      const createdDeck = await createDeckApi({
        name: newDeckName.trim(),
        format: newDeckFormat.trim() || null,
        description: newDeckDescription.trim() || null,
      });

      const newDeckId = String(createdDeck.id);
      setSelectedDeckId(newDeckId);

      const data = await importDecklistApi({
        deckId: newDeckId,
        decklist: importDecklistText,
        replaceExisting: replaceExistingImport,
      });

      setImportResult(data);
      setNewDeckName("");
      setNewDeckDescription("");

      await loadDecks();

      const deckId = Number(newDeckId);
      await Promise.all([loadSelectedDeck(deckId), loadDeckAnalysis(deckId), loadDeckHealth(deckId)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create deck from import");
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
      const data = await exportDecklistApi(selectedDeckId);
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

  async function runDeckCoach() {
    if (!selectedDeckId) {
      setError("Create or select a deck first");
      return;
    }

    setCoachLoading(true);
    setError("");
    setCoachReport("");
    setCoachGoalUsed("");
    setCoachSuggestions([]);

    try {
      const data = await runDeckCoachApi({
        deckId: selectedDeckId,
        goal: coachGoal,
        maxManaValue: coachMaxManaValue,
        suggestionLimit: 5,
        includeToolPayloads: true,
      });

      setCoachReport(data.coach_report);
      setCoachGoalUsed(data.goal_used ?? "");
      setCoachSuggestions(data.tool_payloads?.suggestions?.suggestions ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not run deck coach");
    } finally {
      setCoachLoading(false);
    }
  }

  function clearError() {
    setError("");
  }

  return useMemo(
    () => ({
      mode,
      setMode,
      name,
      setName,
      text,
      setText,
      color,
      setColor,
      maxManaValue,
      setMaxManaValue,
      semanticQuery,
      setSemanticQuery,
      cards,
      loading,
      error,
      clearError,
      decks,
      selectedDeckId,
      setSelectedDeckId,
      selectedDeck,
      deckAnalysis,
      newDeckName,
      setNewDeckName,
      newDeckFormat,
      setNewDeckFormat,
      newDeckDescription,
      setNewDeckDescription,
      suggestionGoal,
      setSuggestionGoal,
      suggestionMaxManaValue,
      setSuggestionMaxManaValue,
      suggestions,
      suggestionsLoading,
      importDecklistText,
      setImportDecklistText,
      replaceExistingImport,
      setReplaceExistingImport,
      importResult,
      exportedDecklist,
      decklistLoading,
      rulesCheck,
      deckDiagnosis,
      deckHealthLoading,
      isCommanderDeck,
      commanderEntry,
      selectedDeckTotalCards,
      coachGoal,
      setCoachGoal,
      coachMaxManaValue,
      setCoachMaxManaValue,
      coachReport,
      coachGoalUsed,
      coachSuggestions,
      coachLoading,
      createDeck,
      handleSearch,
      loadDeckSuggestions,
      addCardToSelectedDeck,
      removeCardFromSelectedDeck,
      setCardAsCommander,
      clearCommander,
      importDecklist,
      createDeckFromImport,
      exportDecklist,
      copyExportedDecklist,
      runDeckCoach,
    }),
    [
      mode,
      name,
      text,
      color,
      maxManaValue,
      semanticQuery,
      cards,
      loading,
      error,
      decks,
      selectedDeckId,
      selectedDeck,
      deckAnalysis,
      newDeckName,
      newDeckFormat,
      newDeckDescription,
      suggestionGoal,
      suggestionMaxManaValue,
      suggestions,
      suggestionsLoading,
      importDecklistText,
      replaceExistingImport,
      importResult,
      exportedDecklist,
      decklistLoading,
      rulesCheck,
      deckDiagnosis,
      deckHealthLoading,
      isCommanderDeck,
      commanderEntry,
      selectedDeckTotalCards,
      coachGoal,
      coachMaxManaValue,
      coachReport,
      coachGoalUsed,
      coachSuggestions,
      coachLoading,
    ],
  );
}

export type DeckLabState = ReturnType<typeof useDeckLab>;
