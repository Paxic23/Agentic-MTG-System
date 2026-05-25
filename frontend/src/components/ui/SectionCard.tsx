import { useState } from "react";
import type { PropsWithChildren, ReactNode } from "react";

type SectionCardProps = PropsWithChildren<{
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  actions?: ReactNode;
}>;

export function SectionCard({
  title,
  subtitle,
  defaultOpen = true,
  actions,
  children,
}: SectionCardProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className="section-card">
      <header className="section-header">
        <button
          className="section-toggle"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          type="button"
        >
          <span className="section-title">{title}</span>
          {subtitle && <span className="section-subtitle">{subtitle}</span>}
        </button>

        <div className="section-actions">{actions}</div>
      </header>

      {open && <div className="section-body">{children}</div>}
    </section>
  );
}
