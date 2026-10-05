const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");

function loadPanel() {
  const dom = new JSDOM("<!doctype html><html><body></body></html>", { runScripts: "outside-only" });
  dom.window.eval(fs.readFileSync(path.join(__dirname, "..", "src", "panel.js"), "utf8"));
  return dom.window;
}

const ANALYSIS = {
  product_id: "abc",
  tracked: true,
  observations: 40,
  honesty: {
    verdict: "misleading", score: 31, confidence: "high", current_price: 990, currency: "INR",
    baseline_price: 1000, real_discount_pct: 1, claimed_discount_pct: 60, mrp: 2500, sale_name: "Sale",
    flags: [{ code: "inflated_mrp", severity: "high", message: "Advertised as 60% off <img src=x onerror=alert(1)>", magnitude: 59 }],
    summary: "Misleading: the real saving is about 1%, not the advertised 60%.",
  },
  recommendation: { action: "neutral", confidence: "medium", reason: "No real discount.", source: "rules" },
};

test("renders the verdict and treats API text as text, not HTML", () => {
  const win = loadPanel();
  // The shadow root is closed, so capture it when the panel creates it.
  let shadow;
  const original = win.HTMLElement.prototype.attachShadow;
  win.HTMLElement.prototype.attachShadow = function (init) {
    shadow = original.call(this, init);
    return shadow;
  };
  const panel = win.DealPanel.createPanel();
  panel.render({ analysis: ANALYSIS, dashboardUrl: "http://127.0.0.1:5173" });

  assert.match(shadow.textContent, /Misleading discount/);
  assert.match(shadow.textContent, /Real saving/);
  assert.equal(shadow.querySelectorAll("img").length, 0, "flag text must not become markup");
  assert.match(shadow.querySelector("a").href, /\?product=abc$/);
  panel.destroy();
  assert.equal(win.document.getElementById("deal-honesty-checker"), null);
});

test("shows a learning state before there is enough history", () => {
  const win = loadPanel();
  let shadow;
  const original = win.HTMLElement.prototype.attachShadow;
  win.HTMLElement.prototype.attachShadow = function (init) { shadow = original.call(this, init); return shadow; };
  const panel = win.DealPanel.createPanel();
  panel.render({ analysis: { ...ANALYSIS, observations: 1, honesty: { ...ANALYSIS.honesty, verdict: "insufficient_data", score: null, flags: [] } } });
  assert.match(shadow.textContent, /Learning this price/);
  assert.match(shadow.textContent, /1 price check so far/);
});
