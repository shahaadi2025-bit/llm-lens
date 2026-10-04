import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { InvestigationView, Notebook } from "./pages/Notebook";
import { ReportView, Reports } from "./pages/Reports";
import { Account } from "./pages/Account";
import { Compare } from "./pages/Compare";
import { Fingerprint } from "./pages/Fingerprint";
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
        <Route path="fingerprint" element={<Fingerprint />} />
        <Route path="compare" element={<Compare />} />
        <Route path="account" element={<Account />} />
        <Route path="reports" element={<Reports />} />
        <Route path="reports/:id" element={<ReportView />} />
        <Route path="notebook" element={<Notebook />} />
        <Route path="notebook/:id" element={<InvestigationView />} />
        <Route path="models" element={<Models />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
