// Responsive audit: every key page at 360/768/1024/1440 px; reports horizontal overflow, elements wider than the viewport
// outside scroll containers, console errors and empty pages. Needs data: pass IDS_JSON (see README) or it audits list pages only.
import fs from "node:fs";
import { BASE, launch } from "./browser.mjs";
const ids = process.env.IDS_JSON ? JSON.parse(fs.readFileSync(process.env.IDS_JSON, "utf8")) : null;
const base = BASE;
const pages = (ids ? [
  ["home", "/"], ["dashboard", "/dashboard"], ["experiments", "/experiments"], ["experiment", `/experiments/${ids.b}`],
  ["followup", `/experiments/${ids.child}`], ["failures", "/failures"], ["explain", `/failures/${ids.fail}`],
  ["fingerprint", "/fingerprint"], ["compare", "/compare"], ["report", `/reports/${ids.report}`], ["models", "/models"], ["account", "/account"],
] : [["home", "/"], ["dashboard", "/dashboard"], ["experiments", "/experiments"], ["failures", "/failures"], ["fingerprint", "/fingerprint"], ["compare", "/compare"], ["models", "/models"], ["account", "/account"]]);
const widths = [360, 768, 1024, 1440];
const browser = await launch();
const problems = [];
for (const [name, path] of pages) {
  for (const w of widths) {
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
    page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text()); });
    await page.setViewport({ width: w, height: 900, deviceScaleFactor: 1 });
    await page.goto(base + path, { waitUntil: "networkidle0", timeout: 30000 });
    if (name === "compare") {
      const opts = await page.$$eval("select option", (os) => os.map((o) => [o.value, o.textContent]).filter((x) => x[0]));
      const sels = await page.$$("select");
      if (sels.length >= 2 && opts.length >= 2) { await sels[0].select(opts[0][0]); await sels[1].select(opts[1][0]); await page.click("form button"); await new Promise((r) => setTimeout(r, 1200)); }
    }
    await new Promise((r) => setTimeout(r, 400));
    const m = await page.evaluate(() => {
      const vw = window.innerWidth;
      const doc = document.documentElement;
      const scrollers = (el) => { for (let p = el.parentElement; p; p = p.parentElement) { const o = getComputedStyle(p).overflowX; if (o === "auto" || o === "scroll" || o === "hidden") return true; } return false; };
      const wide = [];
      for (const el of document.querySelectorAll("body *")) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.right > vw + 1 && !scrollers(el)) wide.push(el.tagName.toLowerCase() + (el.className && typeof el.className === "string" ? "." + el.className.split(" ")[0] : "") + ` right=${Math.round(r.right)}`);
      }
      const small = [...document.querySelectorAll("button, a, select, input")].filter((el) => { const r = el.getBoundingClientRect(); return r.width > 0 && (r.height < 24 || r.width < 24); }).length;
      return { pageOverflow: doc.scrollWidth > vw + 1, scrollWidth: doc.scrollWidth, wide: wide.slice(0, 4), tinyTargets: small, text: document.body.innerText.length };
    });
    if (m.pageOverflow || m.wide.length || errors.length || m.text < 50) problems.push({ name, w, ...m, errors });
    if ([360, 1440].includes(w) || name === "experiment" && w === 768) { fs.mkdirSync("out", { recursive: true }); await page.screenshot({ path: `out/${name}-${w}.png`, fullPage: false }); }
    await page.close();
  }
}
await browser.close();
console.log(problems.length ? JSON.stringify(problems, null, 1) : "NO PROBLEMS: no page overflow, no wide elements outside scroll containers, no console errors");
