import { useMemo, useState } from "react";
import { runGeneralChat } from "../api";
import { SectionCard } from "../components/ui/SectionCard";
import type { DeckLabState } from "../hooks/useDeckLab";
import type { GeneralChatMessage } from "../types";

type GeneralChatPageProps = {
  lab: DeckLabState;
};

type DeckContextMode = "active" | "all";

function renderInline(text: string) {
  const nodes: Array<string | JSX.Element> = [];
  const boldPattern = /\*\*(.+?)\*\*/g;

  let cursor = 0;
  let match = boldPattern.exec(text);
  while (match) {
    if (match.index > cursor) {
      nodes.push(text.slice(cursor, match.index));
    }

    nodes.push(<strong key={`bold-${cursor}`}>{match[1]}</strong>);
    cursor = match.index + match[0].length;
    match = boldPattern.exec(text);
  }

  if (cursor < text.length) {
    nodes.push(text.slice(cursor));
  }

  return nodes.length > 0 ? nodes : [text];
}

function renderAssistantMessage(content: string) {
  const blocks = content
    .split(/\n\s*\n/)
    .map((block) => block.trim())
    .filter(Boolean);

  return blocks.map((block, blockIndex) => {
    const lines = block
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    const headingMatch = lines[0]?.match(/^(#{1,3})\s+(.+)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const headingText = headingMatch[2];
      const HeadingTag = level === 1 ? "h2" : level === 2 ? "h3" : "h4";
      const bodyLines = lines.slice(1);

      return (
        <section key={`block-${blockIndex}`}>
          <HeadingTag>{renderInline(headingText)}</HeadingTag>
          {bodyLines.length > 0 && <p>{renderInline(bodyLines.join(" "))}</p>}
        </section>
      );
    }

    const isList = lines.every((line) => /^[-*]\s+/.test(line));
    if (isList) {
      return (
        <ul key={`block-${blockIndex}`}>
          {lines.map((line, lineIndex) => (
            <li key={`item-${blockIndex}-${lineIndex}`}>{renderInline(line.replace(/^[-*]\s+/, ""))}</li>
          ))}
        </ul>
      );
    }

    return <p key={`block-${blockIndex}`}>{renderInline(lines.join(" "))}</p>;
  });
}

export function GeneralChatPage({ lab }: GeneralChatPageProps) {
  const [messages, setMessages] = useState<GeneralChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [chatError, setChatError] = useState("");
  const [includeDeckContext, setIncludeDeckContext] = useState(false);
  const [deckContextMode, setDeckContextMode] = useState<DeckContextMode>("active");

  const activeDeckId = lab.selectedDeckId ? Number(lab.selectedDeckId) : null;

  const contextHint = useMemo(() => {
    if (!includeDeckContext) {
      return "Deck context is OFF. The assistant will answer from general MTG knowledge only.";
    }

    if (deckContextMode === "active") {
      return activeDeckId
        ? "Deck context is ON for the active deck only."
        : "Deck context is ON, but no active deck is selected.";
    }

    return "Deck context is ON for all decks in your database.";
  }, [activeDeckId, deckContextMode, includeDeckContext]);

  async function sendMessage() {
    const text = draft.trim();
    if (!text || loading) {
      return;
    }

    if (includeDeckContext && deckContextMode === "active" && !activeDeckId) {
      setChatError("Select an active deck or switch context mode to all decks.");
      return;
    }

    const nextMessages: GeneralChatMessage[] = [
      ...messages,
      { role: "user", content: text },
    ];

    setMessages(nextMessages);
    setDraft("");
    setChatError("");
    setLoading(true);

    try {
      const deckIds = includeDeckContext
        ? deckContextMode === "active"
          ? activeDeckId
            ? [activeDeckId]
            : []
          : []
        : [];

      const response = await runGeneralChat({
        messages: nextMessages,
        includeDeckContext,
        deckIds,
      });

      setMessages([
        ...nextMessages,
        { role: "assistant", content: response.reply },
      ]);
    } catch (err) {
      setChatError(err instanceof Error ? err.message : "Could not get AI response");
      setMessages(messages);
      setDraft(text);
    } finally {
      setLoading(false);
    }
  }

  function clearChat() {
    if (loading) {
      return;
    }
    setMessages([]);
    setDraft("");
    setChatError("");
  }

  return (
    <div className="stack">
      <SectionCard
        title="General Chat"
        subtitle="Discuss MTG freely. Decks are not used unless you explicitly enable context."
        actions={
          <button className="secondary-button no-margin" onClick={clearChat} type="button" disabled={loading}>
            Clear chat
          </button>
        }
      >
        <div className="chat-context-controls">
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={includeDeckContext}
              onChange={(event) => setIncludeDeckContext(event.target.checked)}
            />
            Include deck database context for this message
          </label>

          {includeDeckContext && (
            <div className="chat-context-mode">
              <label className="checkbox-row">
                <input
                  type="radio"
                  name="deck-context-mode"
                  checked={deckContextMode === "active"}
                  onChange={() => setDeckContextMode("active")}
                />
                Use active deck only
              </label>

              <label className="checkbox-row">
                <input
                  type="radio"
                  name="deck-context-mode"
                  checked={deckContextMode === "all"}
                  onChange={() => setDeckContextMode("all")}
                />
                Use all decks in database
              </label>
            </div>
          )}

          <p className="muted helper-note">{contextHint}</p>
        </div>

        <div className="chat-thread" role="log" aria-live="polite">
          {messages.length === 0 && (
            <p className="muted">
              Start a conversation about deck ideas, rules interactions, formats, archetypes, mulligans, sideboarding, or card evaluations.
            </p>
          )}

          {messages.map((message, index) => (
            <article
              key={`${message.role}-${index}`}
              className={`chat-message ${message.role === "user" ? "chat-message-user" : "chat-message-assistant"}`}
            >
              <header>{message.role === "user" ? "You" : "Assistant"}</header>
              {message.role === "assistant" ? (
                <div className="chat-markdown">
                  {renderAssistantMessage(message.content)}
                </div>
              ) : (
                <p>{message.content}</p>
              )}
            </article>
          ))}

          {loading && (
            <article className="chat-message chat-message-assistant">
              <header>Assistant</header>
              <p>Thinking...</p>
            </article>
          )}
        </div>

        {chatError && (
          <div className="global-error" role="alert">
            <p>{chatError}</p>
            <button onClick={() => setChatError("")} type="button">
              Dismiss
            </button>
          </div>
        )}

        <label className="field">
          <span>Message</span>
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Ask anything MTG-related..."
          />
        </label>

        <button className="primary-button" onClick={sendMessage} disabled={loading || !draft.trim()} type="button">
          {loading ? "Sending..." : "Send"}
        </button>
      </SectionCard>
    </div>
  );
}
