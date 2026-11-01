import { html } from "./vendor/lit.js";

const PANEL_VERSION = "1.0.1";

async function loadPage(module) {
  return import(
    `./pages/${module}.js?v=${PANEL_VERSION}`
  );
}

export const router = {

  "/dashboard": (hass) =>
    loadPage("dashboard").then(() =>
      html`
        <microlife-dashboard
          .hass=${hass}
        ></microlife-dashboard>
      `
    ),

  "/history": (hass) =>
    loadPage("history").then(() =>
      html`
        <microlife-history
          .hass=${hass}
        ></microlife-history>
      `
    ),

  "/export": (hass) =>
    loadPage("export").then((mod) =>
      mod.renderExport(hass)
    ),

  "/correction": (hass) =>
    loadPage("correction").then((mod) =>
      mod.renderCorrection(hass)
    ),

  "/device": (hass) =>
    loadPage("device").then((mod) =>
      mod.renderDevice(hass)
    ),

  "/error": (hass) =>
    loadPage("error").then((mod) =>
      mod.renderError(hass)
    ),

};

let _currentPath =
  "/dashboard";

const _history = [
  "/dashboard"
];

export function navigate(path) {

  if (_currentPath !== path) {
    _history.push(path);
  }

  _currentPath = path;
}

export function goBack() {

  if (_history.length <= 1) {
    return;
  }

  _history.pop();

  const previous =
    _history.pop() ||
    "/dashboard";

  navigate(previous);
}

export function currentPath() {
  return _currentPath;
}