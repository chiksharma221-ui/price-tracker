const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");
const { extractObservation } = require("../src/extractors.js");

const FIXTURES = path.join(__dirname, "..", "..", "tests", "fixtures");

function page(file, url) {
  const html = fs.readFileSync(path.join(FIXTURES, file), "utf8");
  const dom = new JSDOM(html, { url });
  return { doc: dom.window.document, loc: dom.window.location };
}

test("reads an Amazon.in product page", () => {
  const { doc, loc } = page("amazon_deal.html", "https://www.amazon.in/boAt-Rockerz/dp/B0TEST1234?ref=x");
  const obs = extractObservation(doc, loc);
  assert.equal(obs.price, 1499);
  assert.equal(obs.mrp, 3990);
  assert.equal(obs.claimed_discount_pct, 62);
  assert.equal(obs.seller, "Appario Retail Private Ltd");
  assert.match(obs.deal_badge, /lightning deal/i);
  assert.equal(obs.name, "boAt Rockerz 550 Bluetooth Headphones");
  assert.equal(obs.in_stock, true);
});

test("reads a Flipkart product page with current class names", () => {
  const { doc, loc } = page("flipkart_deal.html", "https://www.flipkart.com/logitech-mx/p/itmabc123?pid=ACC1");
  const obs = extractObservation(doc, loc);
  assert.equal(obs.price, 7495);
  assert.equal(obs.mrp, 10995);
  assert.equal(obs.claimed_discount_pct, 31);
  assert.equal(obs.seller, "RetailNet");
});

test("ignores search and listing pages", () => {
  const { doc, loc } = page("amazon_deal.html", "https://www.amazon.in/s?k=headphones");
  assert.equal(extractObservation(doc, loc), null);
});

test("ignores unsupported sites", () => {
  const { doc, loc } = page("amazon_deal.html", "https://example.com/dp/B0TEST1234");
  assert.equal(extractObservation(doc, loc), null);
});

test("drops an MRP that is not above the price", () => {
  const html = `<span id="productTitle">X</span><div id="corePriceDisplay_desktop_feature_div">
    <span class="a-price"><span class="a-offscreen">₹999</span></span>
    <span class="basisPrice"><span class="a-price a-text-price"><span class="a-offscreen">₹999</span></span></span></div>`;
  const dom = new JSDOM(html, { url: "https://www.amazon.in/dp/B0TEST1234" });
  const obs = extractObservation(dom.window.document, dom.window.location);
  assert.equal(obs.mrp, null);
  assert.equal(obs.claimed_discount_pct, null);
});

test("falls back to JSON-LD when the price element is missing", () => {
  const html = `<span id="productTitle">Mixer</span>
    <script type="application/ld+json">{"@type":"Product","offers":{"price":"2999","priceCurrency":"INR"}}</script>`;
  const dom = new JSDOM(html, { url: "https://www.amazon.in/dp/B0TEST1234" });
  assert.equal(extractObservation(dom.window.document, dom.window.location).price, 2999);
});
