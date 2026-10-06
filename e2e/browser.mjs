// Launch a browser: CHROME_PATH (your installed Chrome/Edge) wins; otherwise the Linux Chromium bundled by @sparticuz/chromium.
import puppeteer from "puppeteer-core";

export async function launch() {
  if (process.env.CHROME_PATH) {
    return puppeteer.launch({ executablePath: process.env.CHROME_PATH, headless: true, args: ["--no-sandbox"] });
  }
  const { default: chromium } = await import("@sparticuz/chromium");
  return puppeteer.launch({ args: [...chromium.args, "--no-sandbox"], executablePath: await chromium.executablePath(), headless: "shell" });
}
export const BASE = (process.env.BASE_URL || "http://localhost:8000").replace(/\/$/, "");
