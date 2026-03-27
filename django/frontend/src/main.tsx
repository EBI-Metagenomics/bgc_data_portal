import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

const basePath =
  document.querySelector('meta[name="base-path"]')?.getAttribute("content") ??
  "";

ReactDOM.createRoot(document.getElementById("dashboard-root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={`${basePath}/dashboard`}>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
