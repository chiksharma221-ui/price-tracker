const LABELS = {
  genuine: "Genuine deal",
  partly_inflated: "Partly inflated",
  misleading: "Misleading discount",
  insufficient_data: "Learning this price",
};

function add(parent, tag, text, cls) {
  const node = document.createElement(tag);
  if (text != null) node.textContent = text;
  if (cls) node.className = cls;
  parent.appendChild(node);
  return node;
}

async function checkConnection(settings) {
  const status = document.getElementById("status");
  try {
    const res = await fetch(`${settings.backendUrl}/api/health`, { signal: AbortSignal.timeout(4000) });
    status.textContent = res.ok ? "Tracker connected" : `Tracker error ${res.status}`;
  } catch (_) {
    status.textContent = "Tracker not reachable";
  }
}

(async () => {
  const settings = await getSettings();
  const content = document.getElementById("content");
  document.getElementById("settings").addEventListener("click", (e) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  });
  checkConnection(settings);

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const key = `tab:${tab && tab.id}`;
  const stored = (await chrome.storage.session.get(key))[key];
  content.replaceChildren();

  if (!stored) {
    add(content, "p", "Open a product page on Amazon.in or Flipkart and the check runs automatically.", "muted");
    return;
  }
  if (stored.error) {
    add(content, "p", stored.error, "error");
    return;
  }
  const { analysis, observation } = stored;
  const h = analysis.honesty;
  add(content, "p", observation.name, "name");
  const verdict = add(content, "p", LABELS[h ? h.verdict : "insufficient_data"], `verdict ${h ? h.verdict : ""}`);
  if (h && h.score != null) add(verdict, "span", ` ${h.score}/100`, "score");
  add(content, "p", h && h.verdict !== "insufficient_data"
    ? h.summary
    : `Tracking this product (${analysis.observations} check${analysis.observations === 1 ? "" : "s"}). A verdict needs about a week of prices.`);
  if (analysis.recommendation) add(content, "p", analysis.recommendation.reason, "muted");
  if (settings.dashboardUrl && analysis.product_id) {
    const link = add(content, "a", "Open full price history", "button");
    link.href = `${settings.dashboardUrl}/?product=${encodeURIComponent(analysis.product_id)}`;
    link.target = "_blank";
  }
})();
