In frontend/src/pages/GeneralChatPage.tsx, make these edits:

1. Change the assistant append after `const response = await runGeneralChat(...)` from:

```ts
setMessages([
  ...nextMessages,
  { role: "assistant", content: response.reply },
]);
```

to:

```ts
setMessages([
  ...nextMessages,
  {
    role: "assistant",
    content: response.reply,
    tool_trace: response.tool_trace ?? [],
  },
]);
```

2. Under the rendered `{message.content}`, add:

```tsx
{message.role === "assistant" && message.tool_trace && message.tool_trace.length > 0 && (
  <div className="tool-trace">
    <strong>Tools used:</strong>
    <ul>
      {message.tool_trace.map((entry, traceIndex) => (
        <li key={`${entry.tool}-${traceIndex}`}>
          {entry.ok ? "✅" : "⚠️"} {entry.tool}
          {entry.summary ? ` — ${entry.summary}` : ""}
          {!entry.ok && entry.error ? ` — ${entry.error}` : ""}
        </li>
      ))}
    </ul>
  </div>
)}
```
