import { NavLink, Outlet } from "react-router-dom";
import type { DeckLabState } from "../../hooks/useDeckLab";
import { useTheme } from "../../theme/ThemeProvider";

type AppShellProps = {
  lab: DeckLabState;
};

const NAV_ITEMS = [
  { to: "/search", label: "Search" },
  { to: "/builder", label: "Builder" },
  { to: "/insights", label: "Insights" },
  { to: "/ai-helper", label: "Coach" },
  { to: "/chat", label: "Chat" },
];

export function AppShell({ lab }: AppShellProps) {
  const { mode, toggleMode } = useTheme();

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <span className="wordmark">decklab</span>

          <nav className="route-nav">
            {NAV_ITEMS.map((item) => (
              <NavLink key={item.to} to={item.to} className={({ isActive }) => (isActive ? "active" : "")}>
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="topbar-actions">
            <select
              className="deck-picker"
              aria-label="Active deck"
              value={lab.selectedDeckId}
              onChange={(event) => lab.setSelectedDeckId(event.target.value)}
            >
              <option value="">No deck selected</option>
              {lab.decks.map((deck) => (
                <option key={deck.id} value={deck.id}>
                  {deck.name}
                </option>
              ))}
            </select>

            <button
              className="theme-toggle"
              onClick={toggleMode}
              type="button"
              aria-label={mode === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              title={mode === "dark" ? "Light theme" : "Dark theme"}
            >
              {mode === "dark" ? "☀" : "☾"}
            </button>
          </div>
        </div>
      </header>

      <div className="app-shell">
        {lab.error && (
          <div className="global-error" role="alert">
            <p>{lab.error}</p>
            <button onClick={lab.clearError} type="button">
              Dismiss
            </button>
          </div>
        )}

        <main className="content-area">
          <Outlet />
        </main>
      </div>
    </>
  );
}
