import { Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import { DashboardShell } from "@/components/DashboardShell";
import { useUrlSync } from "@/hooks/use-url-sync";

function App() {
  useUrlSync();

  return (
    <>
      <Routes>
        <Route path="*" element={<DashboardShell />} />
      </Routes>
      <Toaster position="bottom-right" />
    </>
  );
}

export default App;
