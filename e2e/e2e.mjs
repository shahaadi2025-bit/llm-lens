// End-to-end journey in a real browser. Usage: BASE_URL=https://your-app.onrender.com node e2e.mjs
// Windows: set CHROME_PATH to chrome.exe or msedge.exe, e.g. $env:CHROME_PATH="C:\Program Files\Google\Chrome\Application\chrome.exe"
import { BASE, launch } from "./browser.mjs";

const results = [];
async function step(name, fn) {
  try { await fn(); results.push([true, name]); console.log("PASS ", name); }
  catch (e) { results.push([false, name]); console.log("FAIL ", name, "\n      ", e.message.split("\n")[0]); throw e; }
}
const text = (page) => page.evaluate(() => document.body.innerText);
async function waitText(page, needle, timeout = 90000) {
  await page.waitForFunction((n) => document.body.innerText.includes(n), { timeout }, needle);
}
async function clickText(page, selector, needle) {
  const ok = await page.evaluate((s, n) => {
    const el = [...document.querySelectorAll(s)].find((e) => e.textContent.trim().startsWith(n) && !e.disabled);
    if (el) { el.click(); return true; }
    return false;
  }, selector, needle);
  if (!ok) throw new Error(`no enabled ${selector} starting with "${needle}"`);
}
async function type(page, label, value) {
  await page.waitForFunction((l) => [...document.querySelectorAll("label")].some((x) => x.textContent.trim().startsWith(l) && x.querySelector("input,textarea")), { timeout: 15000 }, label);
  const handle = await page.evaluateHandle((l) => [...document.querySelectorAll("label")].find((x) => x.textContent.trim().startsWith(l))?.querySelector("input,textarea"), label);
  const el = handle.asElement();
  if (!el) throw new Error(`no input labelled "${label}"`);
  await el.click({ clickCount: 3 });
  await el.type(value);
}
const expId = (page) => new URL(page.url()).pathname.split("/").pop();

const browser = await launch();
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 900 });
const consoleErrors = [];
page.on("pageerror", (e) => consoleErrors.push(e.message));
page.on("console", (m) => { if (m.type() === "error" && !m.text().includes("401") && !m.text().includes("404")) consoleErrors.push(m.text()); });
let exitCode = 0;
try {
  await step("home page loads with the evidence ladder", async () => {
    await page.goto(BASE + "/", { waitUntil: "networkidle0" });
    await waitText(page, "What a claim has to earn", 30000);
    const t = await text(page);
    for (const w of ["Observation", "Correlation", "Hypothesis", "Supported conclusion", "Run experiment"]) if (!t.includes(w)) throw new Error("missing " + w);
  });

  let anonId;
  await step("anonymous visitor runs an experiment from the form and sees metrics with intervals", async () => {
    await page.goto(BASE + "/experiments", { waitUntil: "networkidle0" });
    await clickText(page, "button", "Run experiment");
    await type(page, "Name", "e2e " + Date.now());
    await type(page, "Seed", String(Math.floor(Math.random() * 1e6)));  // identical specs are rejected as duplicates
    await clickText(page, "button", "Create and run");
    await page.waitForFunction(() => /\/experiments\/[0-9a-f-]{36}/.test(location.pathname), { timeout: 30000 });
    anonId = expId(page);
    await waitText(page, "completed");
    await page.waitForFunction(() => /n=\d+/.test(document.body.innerText) && /method: wilson-95/.test(document.body.innerText), { timeout: 30000 });
    const t = await text(page);
    if (!/Shared demo sandbox|Private|Public/.test(t)) throw new Error("no visibility label");
  });

  await step("evidence behind a metric can be expanded to prompts and responses", async () => {
    await clickText(page, "button", "Show evidence");
    await waitText(page, "runs behind this number", 15000);
    const t = await text(page);
    if (!/numeric_match/.test(t)) throw new Error("evaluator not shown in evidence");
  });

  await step("research report is generated with 14 sections", async () => {
    await clickText(page, "button", "Generate research report");
    await page.waitForFunction(() => location.pathname.startsWith("/reports/"), { timeout: 30000 });
    await waitText(page, "14. Conclusion", 15000);
    const heads = await page.$$eval("h2", (hs) => hs.map((h) => h.textContent).filter((t) => /^\d+\. /.test(t)));
    if (heads.length !== 14) throw new Error(`expected 14 numbered sections, got ${heads.length}`);
    if (!(await text(page)).includes("internal mechanisms")) throw new Error("mechanism disclaimer missing");
  });

  const email = `e2e-${Date.now()}@example.com`;
  await step("a visitor can create an account", async () => {
    await page.goto(BASE + "/account", { waitUntil: "networkidle0" });
    await clickText(page, "button", "No account?");
    await type(page, "Email", email);
    await type(page, "Password", "correct horse battery");
    await clickText(page, "button", "Create account");
    await waitText(page, "private until you make them public", 20000);
  });

  let privateId;
  await step("a signed-in user's experiment is private", async () => {
    await page.goto(BASE + "/experiments", { waitUntil: "networkidle0" });
    await clickText(page, "button", "Run experiment");
    await type(page, "Name", "private e2e " + Date.now());
    await type(page, "Seed", String(Math.floor(Math.random() * 1e6)));
    await clickText(page, "button", "Create and run");
    await page.waitForFunction(() => /\/experiments\/[0-9a-f-]{36}/.test(location.pathname), { timeout: 30000 });
    privateId = expId(page);
    await waitText(page, "Private", 20000);
    await waitText(page, "completed");
  });

  await step("after signing out the private experiment is gone, the anonymous one remains", async () => {
    await page.goto(BASE + "/account", { waitUntil: "networkidle0" });
    await clickText(page, "button", "Sign out");
    await waitText(page, "Create an account", 10000).catch(() => waitText(page, "Sign in", 10000));
    await page.goto(`${BASE}/experiments/${privateId}`, { waitUntil: "networkidle0" });
    await waitText(page, "not found", 15000);
    await page.goto(`${BASE}/experiments/${anonId}`, { waitUntil: "networkidle0" });
    await waitText(page, "completed", 15000);
  });

  await step("the layout does not overflow on a 360px phone", async () => {
    await page.setViewport({ width: 360, height: 800 });
    for (const path of ["/", "/dashboard", `/experiments/${anonId}`, "/fingerprint"]) {
      await page.goto(BASE + path, { waitUntil: "networkidle0" });
      const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (over > 1) throw new Error(`${path} overflows by ${over}px`);
    }
  });

  await step("no unexpected browser console errors during the journey", async () => {
    if (consoleErrors.length) throw new Error(consoleErrors.slice(0, 3).join(" | "));
  });
} catch {
  exitCode = 1;
} finally {
  await browser.close();
}
const failed = results.filter((r) => !r[0]).length;
console.log(`\n${results.length - failed}/${results.length} steps passed${failed ? " (stopped at first failure)" : ""}`);
process.exit(exitCode);
