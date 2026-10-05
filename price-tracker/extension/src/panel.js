/*
 * The on-page result card. Rendered inside a closed shadow root so the
 * shopping site's CSS can't restyle it and ours can't leak into the page.
 * All text is set with textContent (never innerHTML), so nothing coming
 * back from the API or the page can inject markup.
 */
(function (root) {
  "use strict";

  const VERDICTS = {
    genuine: { label: "Genuine deal", color: "#34d399" },
    partly_inflated: { label: "Partly inflated", color: "#fbbf24" },
    misleading: { label: "Misleading discount", color: "#fb7185" },
    insufficient_data: { label: "Learning this price", color: "#a1a1aa" },
  };
  const ACTIONS = { buy: "Good time to buy", wait: "Better to wait", neutral: "No rush to buy" };
  const DOTS = { high: "#fb7185", medium: "#fbbf24", low: "#a1a1aa" };
  const SVG_NS = "http://www.w3.org/2000/svg";

  const STYLE = `
    :host { all: initial; }
    .card { position: fixed; right: 18px; bottom: 18px; z-index: 2147483647; width: 304px; max-width: calc(100vw - 36px);
      font: 13px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: #e7e9ee;
      background: #12141b; border: 1px solid rgba(255,255,255,.12); border-radius: 14px;
      box-shadow: 0 18px 50px rgba(0,0,0,.35); overflow: hidden; }
    .top { display: flex; gap: 12px; align-items: center; padding: 14px 14px 10px; }
    .ring { flex: none; position: relative; width: 46px; height: 46px; }
    .ring svg { transform: rotate(-90deg); display: block; }
    .ring b { position: absolute; inset: 0; display: grid; place-items: center; font-size: 14px; }
    .verdict { font-weight: 650; font-size: 14px; }
    .sub { color: rgba(255,255,255,.45); font-size: 11.5px; }
    .close { margin-left: auto; align-self: flex-start; background: none; border: 0; color: rgba(255,255,255,.5);
      font-size: 18px; line-height: 1; cursor: pointer; padding: 2px 6px; border-radius: 6px; }
    .close:hover { color: #fff; background: rgba(255,255,255,.08); }
    .body { padding: 0 14px 14px; }
    .summary { margin: 0 0 10px; color: rgba(255,255,255,.82); }
    .nums { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 10px; }
    .num { background: rgba(255,255,255,.05); border-radius: 8px; padding: 6px 4px; text-align: center; }
    .num span { display: block; color: rgba(255,255,255,.45); font-size: 10.5px; }
    .num strong { font-size: 14px; }
    ul { margin: 0 0 10px; padding: 0; list-style: none; }
    li { position: relative; padding-left: 12px; margin-bottom: 6px; color: rgba(255,255,255,.72); font-size: 12px; }
    li::before { content: ""; position: absolute; left: 0; top: 7px; width: 5px; height: 5px; border-radius: 50%; background: var(--dot); }
    .rec { border-top: 1px solid rgba(255,255,255,.08); padding-top: 10px; font-size: 12px; color: rgba(255,255,255,.68); }
    .rec strong { color: #fff; }
    .foot { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; font-size: 11px; color: rgba(255,255,255,.38); }
    a { color: #a5b4fc; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .pill { position: fixed; right: 18px; bottom: 18px; z-index: 2147483647; display: flex; gap: 8px; align-items: center;
      background: #12141b; color: #fff; border: 1px solid rgba(255,255,255,.14); border-radius: 999px;
      padding: 8px 12px; font: 600 12.5px system-ui, sans-serif; cursor: pointer; box-shadow: 0 10px 30px rgba(0,0,0,.3); }
    .dot { width: 9px; height: 9px; border-radius: 50%; }
    button:focus-visible, a:focus-visible, .pill:focus-visible { outline: 2px solid #a5b4fc; outline-offset: 2px; }
  `;

  function money(value) {
    return value == null ? "—" : "₹" + Math.round(value).toLocaleString("en-IN");
  }

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => {
      if (v == null) return;
      if (k === "text") node.textContent = v;
      else if (k === "style") node.style.cssText = v;
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    });
    (children || []).forEach((c) => c && node.appendChild(c));
    return node;
  }

  function circle(r, stroke, width, dash) {
    const c = document.createElementNS(SVG_NS, "circle");
    c.setAttribute("cx", "23");
    c.setAttribute("cy", "23");
    c.setAttribute("r", String(r));
    c.setAttribute("fill", "none");
    c.setAttribute("stroke", stroke);
    c.setAttribute("stroke-width", String(width));
    if (dash) {
      c.setAttribute("stroke-linecap", "round");
      c.setAttribute("stroke-dasharray", dash);
    }
    return c;
  }

  function ring(score, color) {
    const width = 5, r = (46 - width) / 2, circ = 2 * Math.PI * r;
    const filled = score == null ? 0 : (score / 100) * circ;
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("width", "46");
    svg.setAttribute("height", "46");
    svg.setAttribute("aria-hidden", "true");
    svg.appendChild(circle(r, "rgba(255,255,255,.1)", width));
    svg.appendChild(circle(r, color, width, `${filled} ${circ}`));
    const wrap = el("div", { class: "ring" });
    wrap.appendChild(svg);
    wrap.appendChild(el("b", { text: score == null ? "?" : String(score), style: `color:${color}` }));
    return wrap;
  }

  function createPanel() {
    const host = document.createElement("div");
    host.id = "deal-honesty-checker";
    const shadow = host.attachShadow({ mode: "closed" });
    shadow.appendChild(el("style", { text: STYLE }));
    const mount = el("div");
    shadow.appendChild(mount);
    document.documentElement.appendChild(host);
    let minimized = false;
    let last = null;

    function render(state) {
      last = state;
      mount.replaceChildren();
      if (minimized) {
        const h = state.analysis && state.analysis.honesty;
        const v = VERDICTS[h ? h.verdict : "insufficient_data"];
        mount.appendChild(el("div", {
          class: "pill", role: "button", tabindex: "0", "aria-label": "Show deal check",
          onclick: expand, onkeydown: (e) => e.key === "Enter" && expand(),
        }, [el("span", { class: "dot", style: `background:${state.error ? "#a1a1aa" : v.color}` }),
            el("span", { text: state.error ? "Deal check" : v.label })]));
        return;
      }
      mount.appendChild(state.error ? errorCard(state) : resultCard(state));
    }

    function expand() { minimized = false; render(last); }
    function minimize() { minimized = true; render(last); }

    function header(color, score, title, sub) {
      return el("div", { class: "top" }, [
        ring(score, color),
        el("div", {}, [el("div", { class: "verdict", text: title, style: `color:${color}` }),
                       el("div", { class: "sub", text: sub })]),
        el("button", { class: "close", "aria-label": "Minimise", text: "×", onclick: minimize }),
      ]);
    }

    function errorCard(state) {
      return el("div", { class: "card", role: "status" }, [
        header("#a1a1aa", null, "Can't reach your tracker", state.backend),
        el("div", { class: "body" }, [
          el("p", { class: "summary", text: state.error }),
          el("div", { class: "foot" }, [
            el("span", { text: "Deal Honesty Checker" }),
            el("a", { href: "#", text: "Settings", onclick: (e) => {
              e.preventDefault();
              chrome.runtime.sendMessage({ type: "openOptions" });
            } }),
          ]),
        ]),
      ]);
    }

    function resultCard(state) {
      const a = state.analysis;
      const h = a.honesty;
      const judged = h && h.verdict !== "insufficient_data";
      const v = VERDICTS[h ? h.verdict : "insufficient_data"];
      const sub = judged
        ? `Honesty score, ${h.confidence} confidence`
        : `${a.observations} price check${a.observations === 1 ? "" : "s"} so far`;
      const body = el("div", { class: "body" });

      if (!judged) {
        body.appendChild(el("p", { class: "summary",
          text: "Tracking started. Judging a discount needs about a week of this product's prices, " +
                "so check back later or leave the tracker running." }));
      } else {
        body.appendChild(el("p", { class: "summary", text: h.summary }));
        body.appendChild(el("div", { class: "nums" }, [
          el("div", { class: "num" }, [el("span", { text: "Advertised" }),
            el("strong", { text: h.claimed_discount_pct != null ? Math.round(h.claimed_discount_pct) + "%" : "—" })]),
          el("div", { class: "num" }, [el("span", { text: "Real saving" }),
            el("strong", { text: h.real_discount_pct != null ? Math.max(0, Math.round(h.real_discount_pct)) + "%" : "—" })]),
          el("div", { class: "num" }, [el("span", { text: "Usual price" }), el("strong", { text: money(h.baseline_price) })]),
        ]));
      }
      if (h && h.flags.length) {
        body.appendChild(el("ul", {}, h.flags.slice(0, 3).map((f) =>
          el("li", { text: f.message, style: `--dot:${DOTS[f.severity] || DOTS.low}` }))));
      }
      if (a.recommendation) {
        body.appendChild(el("div", { class: "rec" }, [
          el("strong", { text: (ACTIONS[a.recommendation.action] || "") + ". " }),
          document.createTextNode(a.recommendation.reason),
        ]));
      }
      body.appendChild(el("div", { class: "foot" }, [
        el("span", { text: "Deal Honesty Checker" }),
        state.dashboardUrl && a.product_id
          ? el("a", { href: `${state.dashboardUrl}/?product=${encodeURIComponent(a.product_id)}`,
                      target: "_blank", rel: "noreferrer", text: "Full price history" })
          : null,
      ]));
      return el("div", { class: "card", role: "status", "aria-live": "polite" },
        [header(v.color, judged ? h.score : null, v.label, sub), body]);
    }

    return { render, destroy: () => host.remove() };
  }

  root.DealPanel = { createPanel };
})(typeof self !== "undefined" ? self : this);
