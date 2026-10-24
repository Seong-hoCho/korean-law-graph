// docs/*.html 지도의 조문 바퀴를 첫 화면 카드용 SVG 축소 그림으로 뽑는다.
// 사용: node tools/thumbs.js privacy insurance
// Playwright가 필요하다. CDN에 닿지 않는 환경이면 CYTOSCAPE_JS에 cytoscape.min.js 경로를 넣는다.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const COLORS = { // graph_template.html 의 :root 토큰과 같은 값
  light: { L: "#1f5a8a", D: "#b26b12", R: "#2c8577", P: "#8a3a6c", delegates: "#b26b12", cites: "#3d7cb5", precedent: "#8a3a6c" },
  dark: { L: "#6aa6da", D: "#e3a14a", R: "#5cc2b1", P: "#d27fb2", delegates: "#e3a14a", cites: "#7fb2e3", precedent: "#d27fb2" },
};
const SIZE = 600;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  if (process.env.CYTOSCAPE_JS) {
    const js = fs.readFileSync(process.env.CYTOSCAPE_JS);
    await page.route("**/cytoscape.min.js", r => r.fulfill({ body: js, contentType: "application/javascript" }));
  }
  for (const name of process.argv.slice(2)) {
    await page.goto("file://" + path.join(ROOT, "docs", name + ".html"));
    await page.waitForFunction(() => typeof cy !== "undefined");
    const g = await page.evaluate(() => ({
      nodes: cy.nodes(":visible").filter(n => !n.hasClass("chapter")).map(n => ({ k: n.data("kind"), s: n.data("size"), gone: n.hasClass("gone"), ...n.position() })),
      edges: cy.edges(":visible").map(e => ({ k: e.data("kind"), a: e.source().position(), b: e.target().position() })),
    }));
    const xs = g.nodes.map(n => n.x), ys = g.nodes.map(n => n.y);
    const x0 = Math.min(...xs), y0 = Math.min(...ys), span = Math.max(Math.max(...xs) - x0, Math.max(...ys) - y0);
    const k = (SIZE - 16) / span, ox = 8 + ((SIZE - 16) - (Math.max(...xs) - x0) * k) / 2, oy = 8 + ((SIZE - 16) - (Math.max(...ys) - y0) * k) / 2;
    const X = v => Math.round(ox + (v - x0) * k), Y = v => Math.round(oy + (v - y0) * k);

    const paths = { delegates: "", cites: "", precedent: "" };
    for (const e of g.edges) if (e.k in paths) paths[e.k] += `M${X(e.a.x)} ${Y(e.a.y)}L${X(e.b.x)} ${Y(e.b.y)}`;
    const dots = { L: "", D: "", R: "", P: "" };
    for (const n of g.nodes) {
      if (!(n.k in dots) || n.gone) continue;
      const r = Math.max(1.2, n.s * k * 0.5).toFixed(1);
      dots[n.k] += `M${X(n.x) - r} ${Y(n.y)}a${r} ${r} 0 1 0 ${r * 2} 0a${r} ${r} 0 1 0 ${-r * 2} 0`;
    }
    const css = c => Object.entries(c).map(([key, v]) => `.${key}{${/^[LDRP]$/.test(key) ? "fill" : "stroke"}:${v}}`).join("");
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${SIZE} ${SIZE}">
<style>path{fill:none}.e{stroke-width:.6}.delegates{stroke-opacity:.5}.cites{stroke-opacity:.18}.precedent{stroke-opacity:.22}${css(COLORS.light)}@media (prefers-color-scheme:dark){${css(COLORS.dark)}}</style>
${Object.entries(paths).map(([kk, d]) => `<path class="e ${kk}" d="${d}"/>`).join("\n")}
${Object.entries(dots).filter(([, d]) => d).map(([kk, d]) => `<path class="${kk}" d="${d}"/>`).join("\n")}
</svg>\n`;
    const out = path.join(ROOT, "docs", "thumbs", name + ".svg");
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, svg);
    console.log(out, (svg.length / 1024).toFixed(0) + " KB");
  }
  await browser.close();
})();
