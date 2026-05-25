import type {
  Card,
  Deck,
  DeckAnalysis,
  DeckCoachResponse,
  DeckDetail,
  DeckDiagnosis,
  DeckExportResult,
  DeckImportResult,
  DeckSuggestionResponse,
  GeneralChatMessage,
  GeneralChatResponse,
  RulesCheck,
} from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function readResponse<T>(response: Response, fallbackError: string): Promise<T> {
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail ?? `${fallbackError}: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function fetchDecks(): Promise<Deck[]> {
  const response = await fetch(`${API_URL}/decks`);
  return readResponse<Deck[]>(response, "Could not load decks");
}

export async function fetchDeck(deckId: number): Promise<DeckDetail> {
  const response = await fetch(`${API_URL}/decks/${deckId}`);
  return readResponse<DeckDetail>(response, "Could not load deck");
}

export async function fetchDeckAnalysis(deckId: number): Promise<DeckAnalysis> {
  const response = await fetch(`${API_URL}/decks/${deckId}/analysis`);
  return readResponse<DeckAnalysis>(response, "Could not load analysis");
}

export async function createDeck(payload: {
  name: string;
  format: string | null;
  description: string | null;
}): Promise<Deck> {
  const response = await fetch(`${API_URL}/decks`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return readResponse<Deck>(response, "Could not create deck");
}

export async function searchCards(payload: {
  name?: string;
  text?: string;
  color?: string;
  maxManaValue?: string;
  limit?: number;
}): Promise<Card[]> {
  const params = new URLSearchParams();

  if (payload.name?.trim()) params.set("name", payload.name.trim());
  if (payload.text?.trim()) params.set("text", payload.text.trim());
  if (payload.color?.trim()) params.set("color", payload.color.trim());
  if (payload.maxManaValue?.trim()) params.set("max_mana_value", payload.maxManaValue.trim());

  params.set("limit", String(payload.limit ?? 50));

  const response = await fetch(`${API_URL}/cards?${params.toString()}`);
  return readResponse<Card[]>(response, "API request failed");
}

export async function semanticSearchCards(payload: {
  query: string;
  color?: string;
  maxManaValue?: string;
  limit?: number;
}): Promise<Card[]> {
  const response = await fetch(`${API_URL}/cards/semantic-search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      query: payload.query,
      limit: payload.limit ?? 25,
      color: payload.color || null,
      max_mana_value: payload.maxManaValue ? Number(payload.maxManaValue) : null,
    }),
  });

  return readResponse<Card[]>(response, "API request failed");
}

export async function fetchDeckSuggestions(payload: {
  deckId: string;
  goal: string;
  maxManaValue?: string;
  limit?: number;
}): Promise<DeckSuggestionResponse> {
  const response = await fetch(`${API_URL}/decks/${payload.deckId}/suggestions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      goal: payload.goal.trim() || null,
      limit: payload.limit ?? 10,
      max_mana_value: payload.maxManaValue ? Number(payload.maxManaValue) : null,
    }),
  });

  return readResponse<DeckSuggestionResponse>(response, "Could not load suggestions");
}

export async function addCardToDeck(payload: {
  deckId: string;
  cardId: number;
  quantity?: number;
}): Promise<unknown> {
  const response = await fetch(`${API_URL}/decks/${payload.deckId}/cards`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      card_id: payload.cardId,
      quantity: payload.quantity ?? 1,
    }),
  });

  return readResponse<unknown>(response, "Could not add card");
}

export async function removeCardFromDeck(payload: {
  deckId: string;
  cardId: number;
}): Promise<{ status: string }> {
  const response = await fetch(`${API_URL}/decks/${payload.deckId}/cards/${payload.cardId}`, {
    method: "DELETE",
  });

  return readResponse<{ status: string }>(response, "Could not remove card");
}

export async function importDecklist(payload: {
  deckId: string;
  decklist: string;
  replaceExisting: boolean;
}): Promise<DeckImportResult> {
  const response = await fetch(`${API_URL}/decks/${payload.deckId}/import`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      decklist: payload.decklist,
      replace_existing: payload.replaceExisting,
    }),
  });

  return readResponse<DeckImportResult>(response, "Could not import decklist");
}

export async function exportDecklist(deckId: string): Promise<DeckExportResult> {
  const response = await fetch(`${API_URL}/decks/${deckId}/export`);
  return readResponse<DeckExportResult>(response, "Could not export decklist");
}

export async function setDeckCommander(payload: {
  deckId: string;
  cardId: number;
}): Promise<unknown> {
  const response = await fetch(`${API_URL}/decks/${payload.deckId}/cards/${payload.cardId}/commander`, {
    method: "PATCH",
  });

  return readResponse<unknown>(response, "Could not set commander");
}

export async function clearDeckCommander(deckId: string): Promise<{ status: string }> {
  const response = await fetch(`${API_URL}/decks/${deckId}/commander`, {
    method: "DELETE",
  });

  return readResponse<{ status: string }>(response, "Could not clear commander");
}

export async function fetchDeckRulesCheck(deckId: number): Promise<RulesCheck> {
  const response = await fetch(`${API_URL}/decks/${deckId}/rules-check`);
  return readResponse<RulesCheck>(response, "Could not load rules check");
}

export async function fetchDeckDiagnosis(deckId: number): Promise<DeckDiagnosis> {
  const response = await fetch(`${API_URL}/decks/${deckId}/diagnosis`);
  return readResponse<DeckDiagnosis>(response, "Could not load deck diagnosis");
}

export async function runDeckCoach(payload: {
  deckId: string;
  goal: string;
  maxManaValue?: string;
  ignoreCategories?: string[];
  suggestionLimit?: number;
  includeToolPayloads?: boolean;
}): Promise<DeckCoachResponse> {
  const response = await fetch(`${API_URL}/agent/deck-coach`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      deck_id: Number(payload.deckId),
      goal: payload.goal.trim() || null,
      suggestion_limit: payload.suggestionLimit ?? 5,
      max_mana_value: payload.maxManaValue ? Number(payload.maxManaValue) : null,
      ignore_categories: payload.ignoreCategories ?? [],
      include_tool_payloads: payload.includeToolPayloads ?? true,
    }),
  });

  return readResponse<DeckCoachResponse>(response, "Could not run deck coach");
}

export async function runGeneralChat(payload: {
  messages: GeneralChatMessage[];
  includeDeckContext?: boolean;
  deckIds?: number[];
}): Promise<GeneralChatResponse> {
  const response = await fetch(`${API_URL}/agent/general-chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      messages: payload.messages,
      include_deck_context: payload.includeDeckContext ?? false,
      deck_ids: payload.deckIds ?? [],
    }),
  });

  return readResponse<GeneralChatResponse>(response, "Could not run general chat");
}
