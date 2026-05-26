// Replace the existing GeneralChatMessage and GeneralChatResponse types in frontend/src/types.ts with these.

export type GeneralChatToolTrace = {
  tool: string;
  arguments: Record<string, unknown>;
  ok: boolean;
  summary: string | null;
  error: string | null;
};

export type GeneralChatMessage = {
  role: "user" | "assistant";
  content: string;
  tool_trace?: GeneralChatToolTrace[];
};

export type GeneralChatResponse = {
  reply: string;
  used_deck_context: boolean;
  referenced_deck_count: number;
  tool_trace: GeneralChatToolTrace[];
};
