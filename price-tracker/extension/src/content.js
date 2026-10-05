/*
 * Runs on Amazon.in and Flipkart pages. On a product page it reads what the
 * shopper is already seeing, asks the tracker for an honesty analysis (via
 * the background worker, which holds the API settings), and shows the
 * result in a small card.
 */
(function () {
  "use strict";

  const RETRIES = 8;
  const RETRY_MS = 700;
  let panel = null;
  let lastUrl = location.href;
  let runId = 0;

  function show(state) {
    if (!panel) panel = window.DealPanel.createPanel();
    panel.render(state);
  }

  function reset() {
    if (panel) panel.destroy();
    panel = null;
  }

  async function run() {
    const myRun = ++runId;
    let observation = null;
    for (let attempt = 0; attempt < RETRIES && !observation; attempt++) {
      observation = window.DealExtractors.extractObservation(document, location);
      if (!observation) await new Promise((r) => setTimeout(r, RETRY_MS)); // prices often render late
      if (myRun !== runId) return; // the user navigated away meanwhile
    }
    if (!observation) return; // not a product page, or no readable price

    let response;
    try {
      response = await chrome.runtime.sendMessage({ type: "analyze", observation });
    } catch (_) {
      return; // extension was reloaded; this content script is orphaned
    }
    if (myRun !== runId || !response || response.autoShow === false) return;
    show(response.ok
      ? { analysis: response.analysis, dashboardUrl: response.dashboardUrl }
      : { error: response.error, backend: response.backend });
  }

  // Flipkart (and some Amazon flows) change product without a full page
  // load, so watch for URL changes.
  setInterval(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      reset();
      run();
    }
  }, 1000);

  run();
})();
