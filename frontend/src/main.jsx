import { createElement } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import Dashboard from "./Dashboard";
import "./index.css";

const path = window.location.pathname.replace(/\/+$/, "") || "/";
const Page = path === "/dashboard" ? Dashboard : App;
createRoot(document.getElementById("root")).render(createElement(Page));
