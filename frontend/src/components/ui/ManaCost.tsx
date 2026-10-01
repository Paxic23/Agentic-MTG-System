const COLOR_LETTERS = new Set(["W", "U", "B", "R", "G"]);

function pipClass(symbol: string) {
  // Hybrid/phyrexian symbols like "W/U" or "G/P" take the first colored letter.
  const colored = symbol.split("/").find((part) => COLOR_LETTERS.has(part));
  return colored ? `pip pip-${colored}` : "pip pip-C";
}

// Non-mana symbols that show up in rules text.
const SPECIAL_LABELS: Record<string, string> = {
  T: "↷",
  Q: "↶",
  S: "❄",
};

function Pip({ symbol, inline = false }: { symbol: string; inline?: boolean }) {
  const label = SPECIAL_LABELS[symbol] ?? symbol.replace("/P", "ᵖ").replace("/", "");
  return (
    <span className={`${pipClass(symbol)} ${inline ? "pip-inline" : ""}`} title={`{${symbol}}`}>
      {label}
    </span>
  );
}

// Renders rules text with {T}, {B}, {2} etc. swapped for pips.
export function SymbolText({ text }: { text: string }) {
  const parts = text.split(/(\{[^}]+\})/g).filter(Boolean);
  return (
    <>
      {parts.map((part, index) => {
        const symbol = part.match(/^\{([^}]+)\}$/);
        return symbol ? <Pip key={index} symbol={symbol[1]} inline /> : part;
      })}
    </>
  );
}

export function ManaCost({ cost }: { cost: string | null | undefined }) {
  if (!cost) {
    return null;
  }

  // Split cards ("{1}{U} // {3}{U}") render each half with a divider.
  const halves = cost.split("//").map((half) => half.trim());

  return (
    <span className="mana-cost" aria-label={cost}>
      {halves.map((half, halfIndex) => (
        <span key={halfIndex} className="mana-cost-half">
          {halfIndex > 0 && <span className="mana-cost-divider">/</span>}
          {Array.from(half.matchAll(/\{([^}]+)\}/g)).map((match, index) => (
            <Pip key={index} symbol={match[1]} />
          ))}
        </span>
      ))}
    </span>
  );
}

export function ColorIdentity({ colors }: { colors: string[] | null | undefined }) {
  if (!colors || colors.length === 0) {
    return <span className="pip pip-C" title="Colorless">C</span>;
  }

  return (
    <span className="mana-cost">
      {colors.map((color) => (
        <Pip key={color} symbol={color} />
      ))}
    </span>
  );
}
