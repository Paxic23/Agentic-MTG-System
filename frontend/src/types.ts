export type Card = {
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

export type Deck = {
  id: number;
  name: string;
  format: string | null;
  description: string | null;
  created_at: string;
};

export type DeckDetail = Deck & {
  cards: {
    quantity: number;
    is_commander: boolean;
    card: Card;
  }[];
};

export type DeckAnalysis = {
  deck: Deck;
  summary: {
    total_cards: number;
    nonland_cards: number;
    land_cards: number;
    average_mana_value: number | null;
  };
  mana_curve: Record<string, number>;
  type_counts: Record<string, number>;
  color_identity_counts: Record<string, number>;
};

export type DeckSuggestion = {
  score: number;
  reason: string;
  card: Card;
};

export type DeckSuggestionResponse = {
  query_used: string;
  deck_colors: string[];
  allowed_colors: string[] | null;
  suggestions: DeckSuggestion[];
};

export type DeckCoachResponse = {
  deck: Deck;
  goal_used: string | null;
  coach_report: string;
  tool_payloads?: {
    suggestions?: DeckSuggestionResponse;
  } | null;
};

export type DeckImportResult = {
  deck_id: number;
  imported_count: number;
  unmatched_count: number;
  skipped_count: number;
  imported: {
    quantity: number;
    card: Card;
  }[];
  unmatched: {
    line: string;
    parsed_name: string;
    quantity: number;
  }[];
  skipped: string[];
};

export type DeckExportResult = {
  deck: Deck;
  decklist: string;
};

export type RulesCheckIssue = {
  severity: "error" | "warning" | "info" | "ok";
  code: string;
  message: string;
};

export type RulesCheck = {
  deck: Deck;
  format: string | null;
  is_valid: boolean;
  total_cards: number;
  issues: RulesCheckIssue[];
};

export type DiagnosisFinding = {
  severity: "error" | "warning" | "info" | "ok";
  category: string;
  message: string;
  suggested_goal: string | null;
};

export type DeckDiagnosis = {
  deck: Deck;
  summary: {
    total_cards: number;
    land_cards: number;
    nonland_cards: number;
    average_mana_value: number | null;
  };
  themes: string[];
  role_counts: Record<string, number>;
  type_counts: Record<string, number>;
  color_counts: Record<string, number>;
  findings: DiagnosisFinding[];
};

export type GeneralChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type GeneralChatResponse = {
  reply: string;
  used_deck_context: boolean;
  referenced_deck_count: number;
};
