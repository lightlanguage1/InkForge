import { useState } from "react";
import { Routes, Route } from "react-router-dom";
import { InviteGate, getToken, clearToken } from "./components/InviteGate";
import { DashboardPage } from "./pages/Dashboard";
import { ProjectLayout } from "./pages/ProjectLayout";
import { OverviewPage } from "./pages/Overview";
import { WritingPage } from "./pages/Writing";
import { CharactersPage } from "./pages/Characters";
import { LocationsPage } from "./pages/Locations";
import { ScenesPage } from "./pages/Scenes";
import { LoopsPage } from "./pages/Loops";
import { FactionsPage } from "./pages/Factions";
import { GoalsPage } from "./pages/Goals";
import { LorePage } from "./pages/Lore";
import { PlotPage } from "./pages/Plot";
import { CheckpointsPage } from "./pages/Checkpoints";
import { SkillsPage } from "./pages/Skills";
import { ReferencesPage } from "./pages/References";
import { RelationshipsPage } from "./pages/Relationships";
import { ReadPage } from "./pages/Read";
import { CompilePage } from "./pages/Compile";

export function App() {
  const [token, setToken] = useState<string | null>(getToken);

  if (!token) return <InviteGate onActivated={setToken} />;

  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/project/:id" element={<ProjectLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="read" element={<ReadPage />} />
        <Route path="writing" element={<WritingPage />} />
        <Route path="characters" element={<CharactersPage />} />
        <Route path="locations" element={<LocationsPage />} />
        <Route path="scenes" element={<ScenesPage />} />
        <Route path="loops" element={<LoopsPage />} />
        <Route path="factions" element={<FactionsPage />} />
        <Route path="relationships" element={<RelationshipsPage />} />
        <Route path="goals" element={<GoalsPage />} />
        <Route path="lore" element={<LorePage />} />
        <Route path="plot" element={<PlotPage />} />
        <Route path="checkpoints" element={<CheckpointsPage />} />
        <Route path="skills" element={<SkillsPage />} />
        <Route path="references" element={<ReferencesPage />} />
        <Route path="compile" element={<CompilePage />} />
      </Route>
    </Routes>
  );
}
