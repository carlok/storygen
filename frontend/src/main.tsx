import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider }  from "@/context/AuthContext";
import { VideoProvider } from "@/context/VideoContext";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { App } from "./App";
import "@/styles/globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <VideoProvider>
            <App />
          </VideoProvider>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>,
);
