/*
 * Service worker: the only part of the extension that talks to the tracker
 * API. Content scripts can't call it directly (the shopping site's page
 * origin would apply), so they message this worker instead.
 */
importScripts("settings.js");

const VERDICT_BADGE = {
  genuine: "#16a34a",
  partly_inflated: "#d97706",
  misleading: "#dc2626",
  insufficient_data: "#71717a",
};

async function postObservation(settings, observation) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const res = await fetch(`${settings.backendUrl}/api/observations`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(settings.apiToken ? { "X-API-Token": settings.apiToken } : {}),
      },
      body: JSON.stringify(observation),
      signal: controller.signal,
    });
    if (res.status === 401) throw new Error("Your tracker needs an API token. Add it in the extension settings.");
    if (!res.ok) throw new Error(`The tracker returned an error (${res.status}).`);
    return await res.json();
  } catch (err) {
    if (err.name === "AbortError") throw new Error("The tracker took too long to answer.");
    if (err instanceof TypeError) {
      throw new Error("Couldn't connect. Check that the tracker API is running, or change its address in settings.");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

async function setBadge(tabId, analysis) {
  const h = analysis && analysis.honesty;
  const judged = h && h.verdict !== "insufficient_data" && h.score != null;
  await chrome.action.setBadgeText({ tabId, text: judged ? String(h.score) : "" });
  if (judged) await chrome.action.setBadgeBackgroundColor({ tabId, color: VERDICT_BADGE[h.verdict] });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "analyze") {
    (async () => {
      const settings = await getSettings();
      const tabId = sender.tab && sender.tab.id;
      try {
        const analysis = await postObservation(settings, message.observation);
        if (tabId != null) {
          await chrome.storage.session.set({ [`tab:${tabId}`]: { analysis, observation: message.observation, at: Date.now() } });
          await setBadge(tabId, analysis);
        }
        sendResponse({ ok: true, analysis, dashboardUrl: settings.dashboardUrl, autoShow: settings.autoShow });
      } catch (err) {
        if (tabId != null) await chrome.storage.session.set({ [`tab:${tabId}`]: { error: err.message, at: Date.now() } });
        sendResponse({ ok: false, error: err.message, backend: settings.backendUrl, autoShow: settings.autoShow });
      }
    })();
    return true; // keep the channel open for the async response
  }
  if (message.type === "openOptions") {
    chrome.runtime.openOptionsPage();
  }
  return false;
});

chrome.tabs.onRemoved.addListener((tabId) => chrome.storage.session.remove(`tab:${tabId}`));
