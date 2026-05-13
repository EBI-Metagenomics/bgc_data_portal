import { Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import { NrbDashboard } from "@/components/discovery/NrbDashboard";
import { DashboardShell } from "@/components/DashboardShell";
import { useUrlSync } from "@/hooks/use-url-sync";

function App() {
  useUrlSync();

  return (
    <>
      <Routes>
        {/* v2 Discovery dashboard (NRB-first). */}
        <Route path="/" element={<NrbDashboard />} />
        {/* Legacy Explore/Query/Assess modes — preserved at /legacy until P4
            cleanup removes them. */}
        <Route path="/legacy/*" element={<DashboardShell />} />
        <Route path="*" element={<NrbDashboard />} />
      </Routes>
      <Toaster position="bottom-right" />
    </>
  );
}

export default App;
