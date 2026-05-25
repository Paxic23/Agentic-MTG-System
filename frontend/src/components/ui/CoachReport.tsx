type CoachReportProps = {
  report: string;
};

type ReportBlock =
  | { type: "h1" | "h2" | "h3"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "bullet-list"; items: string[] }
  | { type: "number-list"; items: string[] }
  | { type: "label"; label: string; detail: string }
  | { type: "spacer" };

function normalizeLine(line: string): string {
  return line.trim();
}

function parseReportBlocks(report: string): ReportBlock[] {
  const lines = report.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReportBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = normalizeLine(lines[index]);

    if (!line) {
      const previous = blocks[blocks.length - 1];
      if (previous && previous.type !== "spacer") {
        blocks.push({ type: "spacer" });
      }
      index += 1;
      continue;
    }

    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      const level = heading[1].length;
      const text = heading[2].trim();
      blocks.push({ type: level === 1 ? "h1" : level === 2 ? "h2" : "h3", text });
      index += 1;
      continue;
    }

    const boldLabel = line.match(/^\*\*(.+?)\*\*\s*:?[ \t]*(.*)$/);
    if (boldLabel) {
      blocks.push({
        type: "label",
        label: boldLabel[1].trim(),
        detail: boldLabel[2].trim(),
      });
      index += 1;
      continue;
    }

    const bulletItem = line.match(/^[-*]\s+(.+)$/);
    if (bulletItem) {
      const items: string[] = [];
      let pointer = index;

      while (pointer < lines.length) {
        const current = normalizeLine(lines[pointer]);
        const bullet = current.match(/^[-*]\s+(.+)$/);
        if (!bullet) {
          break;
        }
        items.push(bullet[1].trim());
        pointer += 1;
      }

      blocks.push({ type: "bullet-list", items });
      index = pointer;
      continue;
    }

    const numberItem = line.match(/^\d+\.\s+(.+)$/);
    if (numberItem) {
      const items: string[] = [];
      let pointer = index;

      while (pointer < lines.length) {
        const current = normalizeLine(lines[pointer]);
        const numbered = current.match(/^\d+\.\s+(.+)$/);
        if (!numbered) {
          break;
        }
        items.push(numbered[1].trim());
        pointer += 1;
      }

      blocks.push({ type: "number-list", items });
      index = pointer;
      continue;
    }

    blocks.push({ type: "paragraph", text: line });
    index += 1;
  }

  if (blocks[blocks.length - 1]?.type === "spacer") {
    blocks.pop();
  }

  return blocks;
}

function renderInlineText(text: string) {
  const segments = text.split(/(\*\*.+?\*\*)/g).filter(Boolean);

  return segments.map((segment, index) => {
    const match = segment.match(/^\*\*(.+)\*\*$/);
    if (match) {
      return <strong key={`${match[1]}-${index}`}>{match[1]}</strong>;
    }
    return <span key={`${segment}-${index}`}>{segment}</span>;
  });
}

export function CoachReport({ report }: CoachReportProps) {
  const blocks = parseReportBlocks(report);

  return (
    <div className="coach-report-content">
      {blocks.map((block, index) => {
        if (block.type === "spacer") {
          return <div key={`spacer-${index}`} className="coach-report-spacer" aria-hidden="true" />;
        }

        if (block.type === "h1") {
          return (
            <h4 key={`h1-${index}`} className="coach-report-title">
              {block.text}
            </h4>
          );
        }

        if (block.type === "h2" || block.type === "h3") {
          return (
            <h5 key={`h2-${index}`} className="coach-report-heading">
              {block.text}
            </h5>
          );
        }

        if (block.type === "label") {
          return (
            <div key={`label-${index}`} className="coach-report-label-row">
              <strong>{block.label}</strong>
              {block.detail ? <p>{renderInlineText(block.detail)}</p> : null}
            </div>
          );
        }

        if (block.type === "bullet-list") {
          return (
            <ul key={`bullets-${index}`} className="coach-report-list">
              {block.items.map((item, itemIndex) => (
                <li key={`${item}-${itemIndex}`}>{renderInlineText(item)}</li>
              ))}
            </ul>
          );
        }

        if (block.type === "number-list") {
          return (
            <ol key={`numbers-${index}`} className="coach-report-list coach-report-list-numbered">
              {block.items.map((item, itemIndex) => (
                <li key={`${item}-${itemIndex}`}>{renderInlineText(item)}</li>
              ))}
            </ol>
          );
        }

        return (
          <p key={`p-${index}`} className="coach-report-paragraph">
            {renderInlineText(block.text)}
          </p>
        );
      })}
    </div>
  );
}