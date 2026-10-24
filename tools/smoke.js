// 브라우저로 docs/의 모든 페이지를 열어 본다: 스크립트 오류가 없는지, 그래프가 그려지는지,
// 주소 끝의 조문(#L:…)으로 열었을 때 그 조문이 선택되는지.
// 사용: node tools/smoke.js        (CDN에 닿지 않으면 CYTOSCAPE_JS에 cytoscape.min.js 경로)
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const maps = JSON.parse(fs.readFileSync(path.join(ROOT, "maps.json"), "utf8"));
const fail = [];

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 860 } });
  if (process.env.CYTOSCAPE_JS) {
    const js = fs.readFileSync(process.env.CYTOSCAPE_JS);
    await ctx.route("**/cytoscape.min.js", r => r.fulfill({ body: js, contentType: "application/javascript" }));
  }
  ctx.on("weberror", e => fail.push(`페이지 오류: ${e.error().message}`));
  const url = p => "file://" + path.join(ROOT, "docs", p);

  for (const { page: name } of maps) {
    const page = await ctx.newPage();
    const errs = [];
    page.on("pageerror", e => errs.push(e.message));
    page.on("console", m => { if (m.type() === "error" && !/fonts\.(googleapis|gstatic)/.test(m.location().url || "")) errs.push(m.text()); });
    await page.goto(url(name + ".html"));
    const ok = await page.waitForFunction(() => typeof cy !== "undefined" && cy.nodes().length > 0, null, { timeout: 15000 }).then(() => true, () => false);
    if (!ok) { fail.push(`${name}: 그래프가 그려지지 않음 ${errs.join(" / ")}`); await page.close(); continue; }
    // 연결이 가장 많은 조문을 주소로 열어 본다
    const id = await page.evaluate(() => G.nodes.filter(n => n.kind === "L").sort((a, b) => cy.$id(b.id).degree() - cy.$id(a.id).degree())[0].id);
    await page.goto(url(name + ".html") + "#" + encodeURI(id));
    await page.waitForTimeout(800);
    const picked = await page.evaluate(() => current);
    const h2 = await page.evaluate(() => document.querySelector("#panel h2")?.textContent || "");
    if (picked !== id || !h2) fail.push(`${name}: #${id} 로 열었는데 선택되지 않음 (선택: ${picked})`);
    if (errs.length) fail.push(`${name}: ${errs.join(" / ")}`);
    console.log(`${name}: 노드 ${await page.evaluate(() => cy.nodes().length)}개, #${id} → ${h2.slice(0, 30)}`);
    await page.close();
  }
  const index = await ctx.newPage();
  await index.goto(url("index.html"));
  const cards = await index.$$eval("a.map", as => as.map(a => a.getAttribute("href")));
  for (const { page: name } of maps) if (!cards.includes(name + ".html")) fail.push(`index.html: ${name} 카드 없음`);
  const broken = await index.$$eval("a.map img", imgs => imgs.filter(i => !i.complete || !i.naturalWidth).map(i => i.getAttribute("src")));
  if (broken.length) fail.push(`index.html: 안 열리는 축소 그림 ${broken.join(", ")}`);
  console.log(`index.html: 카드 ${cards.length}개`);
  await browser.close();

  if (fail.length) { console.error("\n확인 실패:\n - " + fail.join("\n - ")); process.exit(1); }
  console.log("\n모든 페이지 정상");
})();
