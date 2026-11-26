// Screenshot real GitHub pages for the Day 6-14 post edits (needs the pages to be public).
// Usage: node capture.cjs [name ...]   (no args = all targets)
const path = require("path");
const { chromium } = require(path.join(process.env.HOME, ".npm/_npx/e41f203b7505f1fb/node_modules/playwright"));
const K = "https://github.com/hrhgit/Project.Keynes";
const T = {
  test:  ["https://github.com/hrhgit/nightrune/pull/35", "#issuecomment-7038451220", ["Resolved findings"]],
  day06: [`${K}/issues/42`, '[data-testid^="timeline-row-border-"]:has-text("Revision proposal for this ticket")'],
  day07: [`${K}/pull/7`, "#issuecomment-7007196818", ["Resolved findings"]],
  day08: [`${K}/pull/48`, "#issuecomment-7080360588", ["Resolved findings"]],
  day09: [`${K}/pull/49`, "#issuecomment-7086024218", ["View low", "Resolved findings"]],
  day11: [`${K}/pull/77`, "#issuecomment-7152349740", ["Overlay savings figures disagree"]],
  day12: [`${K}/pull/80`, "#issuecomment-7152707651", ["Speed test table omits"]],
  day13: [`${K}/blob/8a87ef12567f3a8df20fd4d5211cd1676f43e3ad/evidence/day13/pr72-report.md`, "article.markdown-body", [], 640],
};
(async () => {
  const names = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(T).filter(n => n !== "test");
  const browser = await chromium.launch({ channel: "chrome" });
  const page = await browser.newPage({ viewport: { width: 1100, height: 1400 }, deviceScaleFactor: 2, colorScheme: "light" });
  for (const n of names) {
    const [url, sel] = T[n];
    const res = await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
    if (!res || res.status() !== 200) { console.log(n, "HTTP", res && res.status()); continue; }
    const el = page.locator(sel).first();
    if (!(await el.count())) { console.log(n, "selector not found", sel); continue; }
    // Optional third entry: open the <details> blocks whose <summary> contains any of these texts
    // (and their enclosing <details>), so the finding the caption names is visible, not collapsed.
    const open = T[n][2] || [];
    if (open.length) {
      const opened = await el.evaluate((root, texts) => {
        let k = 0;
        for (const s of root.querySelectorAll("details > summary")) {
          if (!texts.some(t => s.textContent.includes(t))) continue;
          for (let d = s.parentElement; d && root.contains(d); d = d.parentElement.closest("details")) { d.open = true; k++; }
        }
        return k;
      }, open);
      if (!opened) console.log(n, "warning: no <details> matched", open);
      await page.waitForTimeout(300);
    }
    // Scroll back to the top so sticky page headers sit in their normal place instead of over the element.
    await el.scrollIntoViewIfNeeded();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);
    const box = await el.boundingBox();
    const sy = await page.evaluate(() => window.scrollY);  // boundingBox is viewport-relative; fullPage clip is page-relative
    const clip = { x: box.x, y: box.y + sy, width: box.width, height: Math.min(box.height, T[n][3] || 1500) };
    const out = path.join(__dirname, "shots", `${n}.png`);
    await page.screenshot({ path: out, clip, fullPage: true });
    console.log(n, "ok", Math.round(box.width) + "x" + Math.round(box.height), clip.height < box.height ? `(cropped to ${clip.height}px)` : "");
  }
  await browser.close();
})();
