/** The browser entry point: mount App into index.html's #root with the tokens loaded. */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import "./styles/theme.css";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("index.html is missing its #root element");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
