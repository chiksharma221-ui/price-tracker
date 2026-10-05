/* Shared settings helpers for the background worker, popup and options page. */
const DEFAULT_SETTINGS = {
  backendUrl: "http://127.0.0.1:8000",
  dashboardUrl: "http://127.0.0.1:5173",
  apiToken: "",
  autoShow: true,
};

async function getSettings() {
  const stored = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  return { ...DEFAULT_SETTINGS, ...stored, backendUrl: stored.backendUrl.replace(/\/+$/, ""),
           dashboardUrl: (stored.dashboardUrl || "").replace(/\/+$/, "") };
}
