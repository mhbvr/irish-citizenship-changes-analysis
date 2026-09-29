# Analysis of the proposed amendment to the citizenship law

**Version 0.12 · 29 September 2026, 17:59 IST**

An individual view of the September 2026 General Scheme of the Irish Nationality and
Citizenship (Amendment) Bill, as a static website: short topic pages, shared navigation,
plain-language arguments, sources and accessible charts.

The site is **plain HTML files**. There is no build step: edit a page, save it, reload
the browser.

## Open or preview

Open **`index.html`** directly in a browser. No installation or server is needed.

For a local HTTP preview, run from this directory:

```sh
python3 -m http.server 8000
```

Then visit <http://localhost:8000/>. To host the site, upload this directory (without
`README.md` and `REVIEW.md` if you prefer) to any static host. All internal
links are relative, so hosting under a subdirectory works.

The production URL is **https://mrphs.cc/position/**. It appears in each page's
`<link rel="canonical">` and `og:url` tags and in `sitemap.xml`; if the address changes,
search and replace it in those places. Configure the host to redirect `/position` to
`/position/` and to serve `index.html` as the directory index. Nothing has been deployed.

## What is here

| Path | What it is |
|---|---|
| `index.html` | Overview: the proposal, what is still unknown, and what it means for Ireland |
| `applicants.html` | 1. Who becomes a citizen: migration controls, routes, nationalities, workers, healthcare, contribution, conclusion |
| `residence.html` | 2. Five years or eight: the European comparison, the missing rationale, uncertainty for people already here, and students and researchers |
| `tests.html`, `income.html`, `proportionality.html`, `revocation.html`, `conclusion.html` | Chapters 3–7 |
| `sources.html` | Source register, data definitions and calculations |
| `care.html`, `certainty.html`, `children.html`, `increase.html`, `ireland.html`, `migration.html`, `research.html`, `workers.html` | Old addresses that redirect to where their content now lives |
| `assets/` | Stylesheet and favicon |
| `data/` | Official-data extracts (CSV), transcribed evidence with page/table locators, `calculations.json`, `sources.json` |
| `research/` | Archived copies of official documents: the Scheme, parliamentary answers, certificate tables, NMBI, Medical Council and ESRI reports, the European Parliament citizenship brief, the EU Visa Strategy, the Hussain judgment |
| `sitemap.xml` | List of pages for search engines |
| `checksums.txt` | SHA-256 of every file in `data/` and `research/` |
| `REVIEW.md` | Critical review of the text (29 September 2026); not part of the website |

## Editing pages

Pages are indented, with one element per line and text wrapped at about 100
characters, so they can be edited in any text editor. A few lines are longer because
a single tag carries a long web address.

Every page repeats the same frame: the header, the menu (twice: the fold-out mobile
menu and the sidebar), the previous/next links and the footer. When you **add, remove,
rename or reorder a page**, update that frame in every page, and mark the current page
in both menus with `aria-current="page"`. Also add or remove it in `sitemap.xml`.

**Citations.** A numbered reference is a `<sup class="citation">` link to the official
source. The numbers run in order of first use within each page, and the
“Sources” list at the bottom of the page repeats them with a link to the research note
on `sources.html`. If you add or remove a citation, renumber that page's citations and
its source list.

**Charts and tables** are static HTML, CSS and inline SVG. Each chart has hover
tooltips (SVG `<title>` or the `title` attribute) and a “Show the data as a table” view.
The numbers in the page, the tooltips and the data table are all typed in, so if a
figure changes, change it in all three. Bar widths are `style="width:…%"` values
relative to the largest bar; line-chart points are coordinates in a 240 × 112 viewBox
with the vertical scale running from 0 (y = 88) to 7,000 (y = 12). Chart colours are
blue `#2a78d6` and orange `#eb6834`, checked for colour-blind and contrast safety.

No JavaScript, external fonts, analytics or tracking are used.

## Version

The version appears in the sidebar and footer of every page (“Version 0.12 · 29 September
2026, 17:59 IST”). When you publish a new version, search and replace that text in all pages and at
the top of this file.

## Checking evidence copies

`checksums.txt` records the SHA-256 of every file in `data/` and `research/`. To confirm
none has changed:

```sh
sha256sum -c checksums.txt
```

If you deliberately replace a data or research file, refresh the list:

```sh
sha256sum data/* research/* > checksums.txt
```

## Research and editorial decisions

Checked 26–28 September 2026. The legal baseline was read from official extracts in
`../citizenship-changes-explained`; official administrative data, original attachments
and the research literature were checked in `../irish-migration-stats`. Additional
research used CSO earnings, education, caring and labour-force statistics, official
permit and immigration guidance, NMBI's 2024 and 2025 registers, the Medical Council's
2024 workforce report, ESRI's June 2026 fiscal and welfare studies, the ESRI integration
monitoring report, and the official Hussain judgment on good character.

The sources page records important limits, including blocked live publisher requests;
archived official answers were inspected when live access failed. Source paths inside
the copied CSVs refer to the migration-statistics project; `source_url`/`pq_url` and
the source register point to the official publishers.

Key distinctions:

- Citizenship grants, applications, decisions, arrivals and employment permits measure
  different things. Permits include renewals.
- “S15 residency” in the Department's route table is the route for spouses and civil
  partners of Irish citizens; “Granted International Protection” covers refugees and
  people with subsidiary protection.
- The permits-against-certificates chart compares nationalities, not individuals: the
  datasets cannot be linked person by person, and certificates include partners and
  children.
- Eight months is the reported 2024/2025 median processing time, not a minimum.
- The OECD fiscal figures average 2006–2018, which includes the post-2008 deficits; all
  three measures are shown, including the one on which both groups are negative.
- The income threshold, prescribed benefits and test arrangements remain unsettled.
- Recruitment, retention and belonging concerns are reasoned risks, not forecasts.
- Test-centre estimates are explicit scenarios: 41,511 applications, two tests, 20%
  additional sittings and 200 operating days, with sensitivity checks.
- Eight revocations in the preceding ten years is confirmed in the September 2026
  official answer. The existing grounds and the Government's security rationale are
  both acknowledged.
