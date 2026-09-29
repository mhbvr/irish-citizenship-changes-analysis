// Builds one PDF of the whole site: node scripts/build-pdf.mjs [output.pdf]
//
// The topic pages are joined in navigation order into a single HTML document,
// with ids prefixed per page so that links between pages become links inside
// the PDF. Chromium (via Playwright) prints it using the site's print styles.

import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const output = resolve(process.argv[2] ?? join(root, "citizenship-analysis.pdf"));
const siteUrl = "https://mrphs.cc/position/";

// Same order as the site navigation.
const pages = [
  "index.html",
  "applicants.html",
  "residence.html",
  "tests.html",
  "income.html",
  "proportionality.html",
  "revocation.html",
  "conclusion.html",
  "sources.html",
];
const slug = (page) => page.replace(/\.html$/, "");

function loadPlaywright() {
  const require = createRequire(import.meta.url);
  try {
    return require("playwright");
  } catch {
    // Fall back to a global install (npm install -g playwright).
    const { execSync } = require("node:child_process");
    const globalRoot = execSync("npm root -g").toString().trim();
    return require(join(globalRoot, "playwright"));
  }
}

function rewriteMain(page, html) {
  const match = html.match(/<main id="main">([\s\S]*?)<\/main>/);
  if (!match) throw new Error(`${page}: no <main id="main"> element`);
  const prefix = slug(page);
  let body = match[1];

  // Print every collapsed section (sources, data tables).
  body = body.replace(/<details(?![^>]*\sopen)/g, "<details open");

  // Page-local ids become "<page>--<id>".
  body = body.replace(/\sid="([^"]+)"/g, ` id="${prefix}--$1"`);

  body = body.replace(/\shref="([^"]*)"/g, (all, href) => {
    if (/^(https?:|mailto:)/.test(href)) return all;
    if (href.startsWith("#")) return ` href="#${prefix}--${href.slice(1)}"`;
    const [file, anchor] = href.split("#");
    if (pages.includes(file)) {
      return ` href="#${anchor ? `${slug(file)}--${anchor}` : `page-${slug(file)}`}"`;
    }
    // Anything else (research copies, data files, old pages) points at the live site.
    return ` href="${new URL(href, siteUrl).href}"`;
  });

  return `<section class="pdf-page" id="page-${prefix}">${body}</section>`;
}

const first = readFileSync(join(root, "index.html"), "utf8");
const title = first.match(/<footer>[\s\S]*?<strong>([^<]+)<\/strong>/)[1];
const version = first
  .match(/<footer>[\s\S]*?(Version [^·]+·[^·]+)·/)[1]
  .replace(/\s+/g, " ")
  .trim();

const sections = pages.map((page) => rewriteMain(page, readFileSync(join(root, page), "utf8")));

const document = `<!doctype html>
<html lang="en-IE">
<head>
<meta charset="utf-8">
<title>${title}</title>
<link rel="stylesheet" href="${pathToFileURL(join(root, "assets/style.css")).href}">
<style>
  @page { size: A4; margin: 18mm 16mm 20mm; }
  body { background: white; }
  main { max-width: none; padding: 0; }
  .pdf-page + .pdf-page { break-before: page; }
  .cover { min-height: 230mm; display: flex; flex-direction: column; justify-content: center; }
  .cover h1 { font-size: 30pt; margin-bottom: 12pt; }
  .cover p { font-size: 13pt; color: var(--muted, #555); }
  .toc ol { padding-left: 18pt; }
  .toc li { margin: 4pt 0; }
  summary { list-style: none; }
  summary::-webkit-details-marker { display: none; }
</style>
</head>
<body>
<main>
<section class="pdf-page cover">
  <h1>${title}</h1>
  <p>An individual view of the September 2026 General Scheme of the Irish Nationality and
  Citizenship (Amendment) Bill.</p>
  <p>${version}</p>
  <p>Online version: <a href="${siteUrl}">${siteUrl}</a></p>
  <nav class="toc"><ol>
    ${pages
      .map((page) => {
        const h1 = readFileSync(join(root, page), "utf8").match(/<h1>([\s\S]*?)<\/h1>/)[1];
        return `<li><a href="#page-${slug(page)}">${h1.replace(/\s+/g, " ").trim()}</a></li>`;
      })
      .join("\n    ")}
  </ol></nav>
</section>
${sections.join("\n")}
</main>
</body>
</html>`;

const work = mkdtempSync(join(tmpdir(), "site-pdf-"));
const htmlPath = join(work, "site.html");
writeFileSync(htmlPath, document);

const { chromium } = loadPlaywright();
const launch = {};
if (process.env.CHROMIUM_PATH) launch.executablePath = process.env.CHROMIUM_PATH;
const browser = await chromium.launch(launch);
try {
  const tab = await browser.newPage();
  await tab.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
  await tab.emulateMedia({ media: "print" });
  await tab.pdf({
    path: output,
    format: "A4",
    printBackground: true,
    preferCSSPageSize: true,
    displayHeaderFooter: true,
    headerTemplate: "<span></span>",
    footerTemplate: `<div style="font-size:8px;width:100%;padding:0 16mm;display:flex;justify-content:space-between;color:#666">
      <span>${title} · ${version}</span>
      <span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`,
  });
} finally {
  await browser.close();
  rmSync(work, { recursive: true, force: true });
}
console.log(`Wrote ${output}`);
