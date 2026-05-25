import { NavLink, Outlet } from "react-router-dom";
import type { DeckLabState } from "../../hooks/useDeckLab";
import { useTheme } from "../../theme/ThemeProvider";

type AppShellProps = {
  lab: DeckLabState;
};

export function AppShell({ lab }: AppShellProps) {
  const { mode, toggleMode } = useTheme();

  return (
    <div className="app-shell">
      <div className="background-layers" aria-hidden="true">
        <div className="bg-shape bg-shape-a" />
        <div className="bg-shape bg-shape-b" />
      </div>

      <header className="topbar">
        <div>
          <p className="eyebrow">Agentic MTG System</p>
          <h1>Deck Lab</h1>
        </div>

        <div className="topbar-actions">
          <label className="deck-picker">
            <span>Active deck</span>
            <select
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
          </label>

          <button className="theme-toggle" onClick={toggleMode} type="button">
            {mode === "dark" ? "Switch to light" : "Switch to dark"}
          </button>
        </div>
      </header>

      <nav className="route-nav">
        <NavLink to="/search" className={({ isActive }) => (isActive ? "active" : "")}>Search</NavLink>
        <NavLink to="/builder" className={({ isActive }) => (isActive ? "active" : "")}>Builder</NavLink>
        <NavLink to="/insights" className={({ isActive }) => (isActive ? "active" : "")}>Insights</NavLink>
        <NavLink to="/ai-helper" className={({ isActive }) => (isActive ? "active" : "")}>AI Helper</NavLink>
      </nav>

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
  );
}
