import { useState } from "react";
import type { ReactNode } from "react";
import type { Card } from "../../types";
import { ColorIdentity, ManaCost, SymbolText } from "./ManaCost";

export type CardTableRow = {
  key: string | number;
  card: Card;
  quantity?: number;
  badge?: ReactNode;
  // Shown under the name instead of the oracle text preview (e.g. a suggestion reason).
  note?: string;
  score?: number;
  highlight?: boolean;
  // Small controls on the collapsed row.
  rowActions?: ReactNode;
  // Buttons inside the expanded detail panel.
  detailActions?: ReactNode;
};

type CardTableProps = {
  rows: CardTableRow[];
  showScore?: boolean;
  showType?: boolean;
  empty?: ReactNode;
};

function scryfallImageUrl(name: string) {
  return `https://api.scryfall.com/cards/named?exact=${encodeURIComponent(name)}&format=image&version=normal`;
}

function scryfallPageUrl(name: string) {
  return `https://scryfall.com/search?q=${encodeURIComponent(`!"${name}"`)}`;
}

function shortType(typeLine: string | null) {
  if (!typeLine) {
    return "";
  }
  // Double-faced cards only show the front face's type in the narrow column.
  return typeLine.split("//")[0].trim();
}

function OracleText({ text }: { text: string }) {
  // Reminder text sits in parentheses; dim it the way it looks on the card.
  const parts = text.split(/(\([^)]*\))/g).filter(Boolean);
  return (
    <p className="card-detail-oracle">
      {parts.map((part, index) =>
        part.startsWith("(") ? (
          <span key={index} className="reminder-text">
            <SymbolText text={part} />
          </span>
        ) : (
          <span key={index}>
            <SymbolText text={part} />
          </span>
        ),
      )}
    </p>
  );
}

function MatchBar({ score }: { score: number }) {
  if (score < 0 || score > 1) {
    return <span className="match-value">{score.toFixed(2)}</span>;
  }

  const percent = Math.round(score * 100);
  return (
    <span className="match" title={`Similarity ${score.toFixed(3)}`}>
      <span className="match-bar">
        <span style={{ width: `${percent}%` }} />
      </span>
      <span className="match-value">{percent}%</span>
    </span>
  );
}

function CardDetail({ row }: { row: CardTableRow }) {
  const { card } = row;
  const [imageFailed, setImageFailed] = useState(false);

  return (
    <div className="card-detail">
      {!imageFailed && (
        <img
          className="card-detail-image"
          src={scryfallImageUrl(card.name)}
          alt={card.name}
          loading="lazy"
          onError={() => setImageFailed(true)}
        />
      )}

      <div className="card-detail-body">
        <p className="card-detail-type">{card.type_line}</p>
        {card.oracle_text ? <OracleText text={card.oracle_text} /> : <p className="muted">No rules text.</p>}

        {row.note && <p className="card-detail-note">{row.note}</p>}

        <div className="card-detail-tags">
          <span className="tag">MV {card.mana_value ?? "–"}</span>
          <span className="tag">
            Identity <ColorIdentity colors={card.color_identity} />
          </span>
          {card.keywords?.map((keyword) => (
            <span key={keyword} className="tag">
              {keyword}
            </span>
          ))}
        </div>

        <div className="card-detail-actions">
          {row.detailActions}
          <a className="text-link" href={scryfallPageUrl(card.name)} target="_blank" rel="noreferrer">
            Scryfall ↗
          </a>
        </div>
      </div>
    </div>
  );
}

export function CardTable({ rows, showScore = false, showType = true, empty }: CardTableProps) {
  const [open, setOpen] = useState<Set<string | number>>(new Set());

  function toggle(key: string | number) {
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  if (rows.length === 0) {
    return <div className="card-table-empty">{empty}</div>;
  }

  const columns = ["card-table", showType ? "with-type" : "", showScore ? "with-score" : ""].filter(Boolean).join(" ");

  return (
    <div className={columns}>
      <div className="card-table-head" aria-hidden="true">
        <span>Name</span>
        <span>Cost</span>
        {showType && <span className="col-type">Type</span>}
        {showScore && <span>Match</span>}
        <span />
      </div>

      {rows.map((row) => {
        const isOpen = open.has(row.key);
        const preview = row.note ?? row.card.oracle_text?.replace(/\n/g, " ");

        return (
          <div key={row.key} className={`card-table-item ${isOpen ? "open" : ""} ${row.highlight ? "highlight" : ""}`}>
            <div className="card-table-row" onClick={() => toggle(row.key)}>
              <div className="col-name">
                <button type="button" className="row-toggle" aria-expanded={isOpen} onClick={(event) => {
                  event.stopPropagation();
                  toggle(row.key);
                }}>
                  <span className="chevron" aria-hidden="true">{isOpen ? "▾" : "▸"}</span>
                  {row.quantity !== undefined && <span className="qty">{row.quantity}</span>}
                  <span className="name">{row.card.name}</span>
                  {row.badge}
                </button>
                {!isOpen && preview && (
                  <span className="preview">
                    <SymbolText text={preview} />
                  </span>
                )}
              </div>
              <div className="col-cost">
                <ManaCost cost={row.card.mana_cost} />
              </div>
              {showType && <div className="col-type">{shortType(row.card.type_line)}</div>}
              {showScore && <div>{row.score !== undefined && <MatchBar score={row.score} />}</div>}
              <div className="col-actions" onClick={(event) => event.stopPropagation()}>
                {row.rowActions}
              </div>
            </div>

            {isOpen && <CardDetail row={row} />}
          </div>
        );
      })}
    </div>
  );
}
