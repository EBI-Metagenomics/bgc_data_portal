import { Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import { IbgcDashboard } from "@/components/discovery/IbgcDashboard";
import { ReportPage } from "@/components/report/ReportPage";
import { useUrlSync } from "@/hooks/use-url-sync";
import { ErrorBoundary } from "@/components/ErrorBoundary";

function App() {
  useUrlSync();

  return (
    <>
      <ErrorBoundary>
        <Routes>
          {/* v2 Discovery dashboard (iBGC-first). */}
          <Route path="/" element={<IbgcDashboard />} />
          {/* Shortlist Report — opened in a new tab via Generate Report. */}
          <Route path="/report" element={<ReportPage />} />
          <Route path="*" element={<IbgcDashboard />} />
        </Routes>
      </ErrorBoundary>
      <Toaster position="bottom-right" />
    </>
  );
}

export default App;
