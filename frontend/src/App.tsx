import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ExplainFailure } from "./pages/ExplainFailure";
import { Failures } from "./pages/Failures";
import { Dashboard } from "./pages/Dashboard";
import { ExperimentDetail } from "./pages/ExperimentDetail";
import { Experiments } from "./pages/Experiments";
import { Home } from "./pages/Home";
import { Models } from "./pages/Models";
import { NotFound } from "./pages/NotFound";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="experiments" element={<Experiments />} />
        <Route path="experiments/:id" element={<ExperimentDetail />} />
        <Route path="failures" element={<Failures />} />
        <Route path="failures/:id" element={<ExplainFailure />} />
        <Route path="models" element={<Models />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
