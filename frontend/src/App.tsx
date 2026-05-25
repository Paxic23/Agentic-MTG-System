import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { useDeckLab } from "./hooks/useDeckLab";
import { AIHelperPage } from "./pages/AIHelperPage";
import { BuilderPage } from "./pages/BuilderPage";
import { GeneralChatPage } from "./pages/GeneralChatPage";
import { InsightsPage } from "./pages/InsightsPage";
import { SearchPage } from "./pages/SearchPage";
import { ThemeProvider } from "./theme/ThemeProvider";

export default function App() {
  const lab = useDeckLab();

  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell lab={lab} />}>
            <Route path="/" element={<Navigate replace to="/search" />} />
            <Route path="/search" element={<SearchPage lab={lab} />} />
            <Route path="/builder" element={<BuilderPage lab={lab} />} />
            <Route path="/insights" element={<InsightsPage lab={lab} />} />
            <Route path="/ai-helper" element={<AIHelperPage lab={lab} />} />
            <Route path="/chat" element={<GeneralChatPage lab={lab} />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}
