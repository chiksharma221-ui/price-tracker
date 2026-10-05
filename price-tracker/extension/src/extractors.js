/*
 * Read price, MRP, advertised discount, seller and deal badge from the
 * product page the shopper is already looking at.
 *
 * Pure functions over a Document, so they run unchanged in the content
 * script and in Node tests (with jsdom). Site class names change often, so
 * each field lists several selector generations and falls back to the
 * page's schema.org JSON-LD where possible.
 */
(function (root) {
  "use strict";

  const BADGE_RE =
    /(lightning deal|deal of the day|limited time deal|lowest price[^.\n]{0,30}|great indian festival|big billion days?)/i;

  function parseAmount(text) {
    if (!text) return null;
    const cleaned = String(text).replace(/[^0-9.]/g, "");
    const match = cleaned.match(/\d+(\.\d{1,2})?/);
    const value = match ? parseFloat(match[0]) : NaN;
    return Number.isFinite(value) && value > 0 ? value : null;
  }

  function parsePercent(text) {
    const match = String(text || "").match(/(\d{1,2}(?:\.\d)?)\s*%/);
    return match ? parseFloat(match[1]) : null;
  }

  function firstText(doc, selectors) {
    for (const sel of selectors) {
      let el = null;
      try {
        el = doc.querySelector(sel);
      } catch (_) {
        continue; // a selector this DOM implementation can't parse
      }
      const text = el && el.textContent && el.textContent.trim();
      if (text) return text.replace(/\s+/g, " ");
    }
    return null;
  }

  function jsonLdOffer(doc) {
    for (const tag of doc.querySelectorAll('script[type="application/ld+json"]')) {
      let data;
      try {
        data = JSON.parse(tag.textContent || "{}");
      } catch (_) {
        continue;
      }
      for (const item of Array.isArray(data) ? data : [data]) {
        if (!item || typeof item !== "object") continue;
        let offers = item.offers;
        if (Array.isArray(offers)) offers = offers[0];
        if (offers && offers.price) {
          return { name: item.name || null, price: parseAmount(offers.price), currency: offers.priceCurrency || "INR" };
        }
      }
    }
    return null;
  }

  const SITES = {
    amazon: {
      match: (loc) => /(^|\.)amazon\.in$/.test(loc.hostname),
      isProductPage: (doc, loc) =>
        /\/(dp|gp\/product|gp\/aw\/d)\/[A-Z0-9]{10}/i.test(loc.pathname) && !!doc.querySelector("#productTitle"),
      name: ["#productTitle"],
      price: [
        "#corePriceDisplay_desktop_feature_div .priceToPay .a-offscreen",
        "#corePriceDisplay_desktop_feature_div span.a-price:not(.a-text-price) .a-offscreen",
        "#corePrice_feature_div span.a-price:not(.a-text-price) .a-offscreen",
        "#priceblock_dealprice",
        "#priceblock_ourprice",
      ],
      mrp: [
        "#corePriceDisplay_desktop_feature_div .basisPrice .a-offscreen",
        "#corePriceDisplay_desktop_feature_div span.a-price.a-text-price .a-offscreen",
        "#corePrice_feature_div span.a-price.a-text-price .a-offscreen",
        "#listPrice",
      ],
      discount: ["#corePriceDisplay_desktop_feature_div .savingsPercentage", ".savingsPercentage"],
      seller: ["#sellerProfileTriggerId", "#merchantInfoFeature_feature_div .offer-display-feature-text-message"],
      badgeArea: ["#dealBadge_feature_div", "#corePriceDisplay_desktop_feature_div", ".dealBadge"],
      outOfStock: (doc) => /currently unavailable|out of stock/i.test(firstText(doc, ["#availability"]) || ""),
    },
    flipkart: {
      match: (loc) => /(^|\.)flipkart\.com$/.test(loc.hostname),
      isProductPage: (_doc, loc) => /\/p\/itm[0-9a-z]+/i.test(loc.pathname),
      name: ["span.VU-ZEz", "span.B_NuCI", "h1 span", "h1"],
      price: ["div.Nx9bqj.CxhGGd", "div.Nx9bqj", "div._30jeq3._16Jk6d", "div._30jeq3"],
      mrp: ["div.yRaY8j", "div._3I9_wc._2p6lqe", "div._3I9_wc"],
      discount: ["div.UkUFwK span", "div._3Ay6Sb span"],
      seller: ["#sellerName span span", "#sellerName span"],
      badgeArea: ["div.UkUFwK", "div._2Tpdn3", "div.CEmiEU"],
      outOfStock: (doc) => /sold out|currently unavailable/i.test(firstText(doc, ["div.Z8JjpR", "div._16FRp0"]) || ""),
    },
  };

  function detectSite(loc) {
    return Object.keys(SITES).find((key) => SITES[key].match(loc)) || null;
  }

  /**
   * Returns an observation ready for POST /api/observations, or null when
   * this isn't a product page or no price could be read.
   */
  function extractObservation(doc, loc) {
    const key = detectSite(loc);
    if (!key) return null;
    const site = SITES[key];
    if (!site.isProductPage(doc, loc)) return null;

    const ld = jsonLdOffer(doc);
    const price = parseAmount(firstText(doc, site.price)) || (ld && ld.price);
    if (!price) return null;

    let mrp = parseAmount(firstText(doc, site.mrp));
    if (mrp && mrp <= price) mrp = null; // a mis-read, not a discount

    let claimed = parsePercent(firstText(doc, site.discount));
    if (claimed == null && mrp) claimed = Math.round(((mrp - price) / mrp) * 1000) / 10;

    const badgeText = site.badgeArea.map((s) => firstText(doc, [s]) || "").join(" ");
    const badge = badgeText.match(BADGE_RE);

    return {
      url: loc.href,
      name: (firstText(doc, site.name) || (ld && ld.name) || doc.title || "").slice(0, 300),
      price,
      currency: "INR",
      mrp: mrp || null,
      claimed_discount_pct: claimed,
      seller: (firstText(doc, site.seller) || "").slice(0, 120) || null,
      deal_badge: badge ? badge[1].trim() : null,
      in_stock: !site.outOfStock(doc),
    };
  }

  const api = { extractObservation, detectSite, parseAmount, parsePercent };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.DealExtractors = api;
})(typeof self !== "undefined" ? self : this);
