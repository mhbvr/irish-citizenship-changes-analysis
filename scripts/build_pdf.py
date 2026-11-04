#!/usr/bin/env python3
"""Build the submission PDF from the site: python3 scripts/build_pdf.py [output.pdf]

The PDF is laid out from scratch with ReportLab, not printed from a browser. It
follows the Houses of the Oireachtas guidance on public consultation submissions
(https://www.oireachtas.ie/en/committees/making-a-submission/guidance/):

* searchable text (embedded TrueType font, no images of text);
* numbered pages ("Page X of Y") and numbered paragraphs;
* an executive summary (summary.md), because the document is over ten pages;
* a brief introduction, the evidence chapter by chapter, and links to every
  publication referred to, with the full address printed in each chapter's
  source list;
* no personal contact details: those belong in the separate covering letter.

The words come unchanged from the site pages and summary.md. Only page furniture
(menus, previous/next links, "show the data" toggles) is dropped, links between
pages become links inside the PDF, and chart data tables move to Annex B.

Options:
  --submitter "Name"   print the submitter's name on the cover (also SUBMITTER)
  --fonts DIR          directory holding Carlito-{Regular,Bold,Italic,BoldItalic}.ttf
                       (also FONT_DIR); Carlito is metric-compatible with Calibri.
"""

import argparse
import html
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag
from reportlab import rl_config
from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    Indenter,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

# Same output for the same input: no build-time timestamps or random ids in the file.
rl_config.invariant = 1

ROOT = Path(__file__).resolve().parent.parent
SITE_URL = "https://mrphs.cc/position/"
COMMITTEE = "Joint Committee on Justice, Home Affairs and Migration"
SCHEME = "General Scheme of the Irish Nationality and Citizenship (Amendment) Bill 2026"

# Site pages in navigation order: (file, label shown above the title, outline label).
PAGES = [
    ("index.html", "Introduction", "Introduction"),
    ("applicants.html", "Chapter 1", "1"),
    ("residence.html", "Chapter 2", "2"),
    ("tests.html", "Chapter 3", "3"),
    ("income.html", "Chapter 4", "4"),
    ("proportionality.html", "Chapter 5", "5"),
    ("revocation.html", "Chapter 6", "6"),
    ("conclusion.html", "Chapter 7", "7"),
    ("sources.html", "Annex A", "A"),
]
PAGE_FILES = [p for p, _, _ in PAGES]


def slug(page):
    return page[: -len(".html")]


# ---------------------------------------------------------------- appearance

GREEN = colors.HexColor("#155b48")
INK = colors.HexColor("#1d2421")
MUTED = colors.HexColor("#5b6762")
RULE = colors.HexColor("#c9d3cf")
TINT = colors.HexColor("#eef3f1")
BLUE = colors.HexColor("#2a78d6")
ORANGE = colors.HexColor("#eb6834")
LINK = "#155b48"

PAGE_W, PAGE_H = A4
MARGIN_X = 22 * mm
MARGIN_TOP = 24 * mm
MARGIN_BOTTOM = 22 * mm
TEXT_W = PAGE_W - 2 * MARGIN_X
NUM_INDENT = 11 * mm  # column for paragraph numbers
BODY = "Carlito"


def register_fonts(font_dir):
    candidates = [font_dir] if font_dir else []
    candidates += [
        "/usr/share/fonts/truetype/crosextra",
        "/usr/share/fonts/truetype/carlito",
        "/usr/share/fonts/carlito",
        str(ROOT / "assets" / "fonts"),
    ]
    for d in candidates:
        if d and (Path(d) / "Carlito-Regular.ttf").exists():
            break
    else:
        sys.exit(
            "Carlito fonts not found. Install fonts-crosextra-carlito or pass --fonts DIR."
        )
    for suffix, name in [
        ("Regular", BODY),
        ("Bold", BODY + "-Bold"),
        ("Italic", BODY + "-Italic"),
        ("BoldItalic", BODY + "-BoldItalic"),
    ]:
        pdfmetrics.registerFont(TTFont(name, str(Path(d) / f"Carlito-{suffix}.ttf")))
    pdfmetrics.registerFontFamily(
        BODY,
        normal=BODY,
        bold=BODY + "-Bold",
        italic=BODY + "-Italic",
        boldItalic=BODY + "-BoldItalic",
    )


def make_styles():
    s = {}
    s["body"] = ParagraphStyle(
        "body", fontName=BODY, fontSize=11, leading=15, textColor=INK, spaceAfter=7
    )
    s["num"] = ParagraphStyle(
        "num",
        parent=s["body"],
        leftIndent=NUM_INDENT,
        bulletIndent=0,
        bulletFontName=BODY,
        bulletFontSize=9.5,
        bulletColor=MUTED,
    )
    s["plain"] = ParagraphStyle("plain", parent=s["body"], leftIndent=NUM_INDENT)
    s["bullet"] = ParagraphStyle(
        "bullet",
        parent=s["body"],
        leftIndent=NUM_INDENT + 6 * mm,
        bulletIndent=NUM_INDENT + 1.5 * mm,
        spaceAfter=4,
    )
    s["see"] = ParagraphStyle(
        "see", parent=s["body"], leftIndent=NUM_INDENT, fontSize=9.5, leading=13,
        textColor=MUTED, spaceBefore=-3, spaceAfter=9,
    )
    s["kicker"] = ParagraphStyle(
        "kicker", fontName=BODY + "-Bold", fontSize=11, leading=14, textColor=GREEN,
        spaceAfter=2,
    )
    s["h1"] = ParagraphStyle(
        "h1", fontName=BODY + "-Bold", fontSize=23, leading=28, textColor=INK,
        spaceAfter=14,
    )
    s["h2"] = ParagraphStyle(
        "h2", fontName=BODY + "-Bold", fontSize=14.5, leading=18, textColor=GREEN,
        spaceBefore=12, spaceAfter=6, keepWithNext=1,
    )
    s["h3"] = ParagraphStyle(
        "h3", fontName=BODY + "-Bold", fontSize=12, leading=15, textColor=INK,
        spaceBefore=8, spaceAfter=4, keepWithNext=1,
    )
    s["caption"] = ParagraphStyle(
        "caption", fontName=BODY + "-Bold", fontSize=10, leading=13, textColor=INK,
        spaceBefore=4, spaceAfter=4, keepWithNext=1,
    )
    s["note"] = ParagraphStyle(
        "note", fontName=BODY, fontSize=9, leading=12, textColor=MUTED, spaceBefore=3,
        spaceAfter=10,
    )
    s["cell"] = ParagraphStyle("cell", fontName=BODY, fontSize=9.5, leading=12, textColor=INK)
    s["cellr"] = ParagraphStyle("cellr", parent=s["cell"], alignment=TA_RIGHT)
    s["cellh"] = ParagraphStyle("cellh", parent=s["cell"], fontName=BODY + "-Bold")
    s["cellhr"] = ParagraphStyle("cellhr", parent=s["cellh"], alignment=TA_RIGHT)
    s["srchead"] = ParagraphStyle(
        "srchead", fontName=BODY + "-Bold", fontSize=12, leading=15, textColor=GREEN,
        spaceBefore=14, spaceAfter=5, keepWithNext=1,
    )
    s["src"] = ParagraphStyle(
        "src", fontName=BODY, fontSize=9.5, leading=12.5, textColor=INK,
        leftIndent=8 * mm, bulletIndent=0, bulletFontName=BODY, spaceAfter=5,
    )
    s["toc0"] = ParagraphStyle(
        "toc0", fontName=BODY + "-Bold", fontSize=11, leading=14, spaceBefore=6,
        textColor=INK,
    )
    s["toc1"] = ParagraphStyle(
        "toc1", fontName=BODY, fontSize=10, leading=13, leftIndent=8 * mm, textColor=INK,
    )
    return s


# ------------------------------------------------------------------- helpers


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def squash(text):
    return re.sub(r"\s+", " ", text)


NUMERIC = re.compile(r"^[−\-+€£]?\s?[\d,.]+\s?(%|k| points)?$")


class Anchor(Flowable):
    """Zero-size named destination, for targets that are not paragraphs."""

    def __init__(self, name):
        super().__init__()
        self.name = name
        self.width = self.height = 0

    def draw(self):
        self.canv.bookmarkHorizontal(self.name, 0, 0)


class Rule(Flowable):
    def __init__(self, width, color=RULE, thickness=0.6, space=6):
        super().__init__()
        self.width, self.color, self.thickness, self.space = width, color, thickness, space
        self.height = space

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, self.space / 2, self.width, self.space / 2)


class Heading(Paragraph):
    """A paragraph that becomes a bookmark and, optionally, a contents entry."""

    def __init__(self, text, style, level, outline_text, key, toc=True):
        super().__init__(text, style)
        self.level, self.outline_text, self.key, self.toc = level, outline_text, key, toc


# ---------------------------------------------------------------- the builder


class Builder:
    def __init__(self, styles):
        self.s = styles
        self.para_no = 0
        self.anchors = set()
        self.links = []  # (target, where) for checking
        self.figure_tables = []  # Annex B entries
        self.pending = []  # anchors waiting for the next flowable
        self.story = []
        self.heading_no = 0

    # --- links -------------------------------------------------------------

    def resolve(self, href, page):
        """Turn a site href into a PDF target: '#name' inside the PDF, or a URL."""
        href = href.strip()
        if href.startswith(SITE_URL):
            href = href[len(SITE_URL):] or "index.html"
        if re.match(r"^(https?:|mailto:)", href):
            return href
        if href.startswith("#"):
            return self.internal(f"{slug(page)}--{href[1:]}", f"page-{slug(page)}")
        file, _, frag = href.partition("#")
        if file in ("", "./"):
            file = "index.html"
        if file in PAGE_FILES:
            if frag:
                return self.internal(f"{slug(file)}--{frag}", f"page-{slug(file)}")
            return self.internal(f"page-{slug(file)}", None)
        # Research copies, data files and old addresses live on the website.
        return SITE_URL + href

    def internal(self, name, fallback):
        if name not in self.known and fallback:
            print(f"warning: no target {name}; linking to {fallback}", file=sys.stderr)
            name = fallback
        self.links.append((name, fallback))
        return "#" + name

    def link(self, href, inner, page):
        target = self.resolve(href, page)
        return f'<a href="{esc(target)}" color="{LINK}">{inner}</a>'

    # --- inline HTML to ReportLab markup ----------------------------------

    def inline(self, node, page, cites):
        out = []
        for child in node.children:
            if isinstance(child, NavigableString):
                if child.__class__.__name__ in ("Comment", "Doctype"):
                    continue
                out.append(esc(str(child)))
                continue
            name = child.name
            classes = child.get("class") or []
            if name == "sup" and "citation" in classes:
                num = re.search(r"\[(\d+)\]", child.get_text()).group(1)
                out.append(f"\x00{num}\x00")
            elif name == "a":
                inner = self.inline(child, page, cites)
                href = child.get("href")
                out.append(self.link(href, inner, page) if href else inner)
            elif name in ("strong", "b"):
                out.append(f"<b>{self.inline(child, page, cites)}</b>")
            elif name in ("em", "i", "cite"):
                out.append(f"<i>{self.inline(child, page, cites)}</i>")
            elif name == "br":
                out.append("<br/>")
            elif name == "sup":
                out.append(f"<super>{self.inline(child, page, cites)}</super>")
            elif name == "sub":
                out.append(f"<sub>{self.inline(child, page, cites)}</sub>")
            else:
                out.append(self.inline(child, page, cites))
        text = "".join(out)
        return text

    def finish(self, text, page, cites):
        """Collapse whitespace and join runs of citations into one superscript."""
        text = squash(text).strip()

        def group(m):
            nums = re.findall(r"\x00(\d+)\x00", m.group(0))
            parts = []
            for n in nums:
                name = f"src-{slug(page)}-{n}"
                self.links.append((name, None))
                parts.append(f'<a href="#{name}" color="{LINK}">{n}</a>')
            return "<super>" + ",".join(parts) + "</super>"

        text = re.sub(r"\s*(?:\x00\d+\x00\s*)+", group, text)
        # A citation run followed directly by text needs a space after it.
        text = re.sub(r"(</super>)(?=[A-Za-z0-9(“‘])", r"\1 ", text)
        return text

    def take_anchors(self):
        names, self.pending = self.pending, []
        return "".join(f'<a name="{n}"/>' for n in names)

    def flush_anchors(self):
        for n in self.pending:
            self.story.append(Anchor(n))
        self.pending = []

    def add_anchor(self, name):
        self.anchors.add(name)
        self.pending.append(name)

    # --- block elements ----------------------------------------------------

    def numbered(self, markup):
        self.para_no += 1
        self.story.append(
            Paragraph(self.take_anchors() + markup, self.s["num"], bulletText=f"{self.para_no}.")
        )

    def heading(self, markup, style, level, toc=True):
        self.heading_no += 1
        key = f"h{self.heading_no}"
        plain = html.unescape(re.sub(r"<[^>]+>", "", markup))
        self.story.append(
            Heading(f'<a name="{key}"/>' + self.take_anchors() + markup, style, level,
                    plain, key, toc)
        )

    def table(self, rows, header_rows, caption=None, note=None, width=None, first_col=None):
        """rows: list of lists of markup strings; header_rows: count of header rows."""
        width = width or (TEXT_W - NUM_INDENT)
        ncols = max(len(r) for r in rows)
        rows = [r + [""] * (ncols - len(r)) for r in rows]
        numeric = []
        for c in range(ncols):
            vals = [re.sub(r"<[^>]+>", "", r[c]).strip() for r in rows[header_rows:]]
            vals = [html.unescape(v) for v in vals if v]
            numeric.append(c > 0 and bool(vals) and all(NUMERIC.match(v) for v in vals))
        # Column widths from content, first column wrapping when space is short.
        natural = []
        for c in range(ncols):
            w = 0
            for i, r in enumerate(rows):
                plain = html.unescape(re.sub(r"<[^>]+>", "", r[c]))
                font = BODY + "-Bold" if (i < header_rows or c == 0) else BODY
                if i < header_rows:
                    # Header words may wrap; size them by their longest word.
                    w = max(w, max((stringWidth(x, font, 9.5) for x in plain.split()), default=0))
                else:
                    w = max(w, stringWidth(plain, font, 9.5))
            natural.append(w + 12)
        if first_col:
            natural[0] = first_col
        rest = sum(natural[1:])
        if sum(natural) > width:
            first = max(width - rest, width * 0.28)
            natural[0] = first
            if first + rest > width:
                scale = (width - first) / rest
                natural = [first] + [w * scale for w in natural[1:]]
        else:
            # Give spare room to the first column, keep numbers compact.
            natural[0] = width - rest
        last = html.unescape(re.sub(r"<[^>]+>", "", rows[-1][0])).strip().lower()
        total = last == "total"
        data = []
        for i, r in enumerate(rows):
            line = []
            for c, cell in enumerate(r):
                head = i < header_rows or (total and i == len(rows) - 1)
                bold = head or c == 0
                if numeric[c]:
                    st = self.s["cellhr"] if head else self.s["cellr"]
                else:
                    st = self.s["cellh"] if bold else self.s["cell"]
                line.append(Paragraph(cell, st))
            data.append(line)
        t = Table(data, colWidths=natural, repeatRows=header_rows, hAlign="LEFT")
        style = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("BACKGROUND", (0, 0), (-1, header_rows - 1), TINT),
            ("LINEABOVE", (0, 0), (-1, 0), 0.9, GREEN),
            ("LINEBELOW", (0, header_rows - 1), (-1, header_rows - 1), 0.6, GREEN),
            ("LINEBELOW", (0, header_rows), (-1, -1), 0.4, RULE),
        ]
        if total:
            style.append(("LINEABOVE", (0, -1), (-1, -1), 0.8, INK))
        t.setStyle(TableStyle(style))
        block = []
        if caption:
            block.append(Paragraph(self.take_anchors() + caption, self.s["caption"]))
        self.flush_anchors()
        block.append(t)
        if note:
            block.append(Paragraph(note, self.s["note"]))
        else:
            block.append(Spacer(1, 10))
        self.story.append(Indenter(left=NUM_INDENT))
        if len(rows) <= 16:
            self.story.append(KeepTogether(block))
        else:
            self.story.extend(block)
        self.story.append(Indenter(left=-NUM_INDENT))

    def html_table(self, table, page, cites, caption_markup=None, note=None):
        rows, header_rows = [], 0
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            rows.append([self.finish(self.inline(c, page, cites), page, cites) for c in cells])
            if tr.find_parent("thead") is not None:
                header_rows += 1
        if not header_rows:
            header_rows = 1
        cap = table.find("caption")
        if caption_markup is None and cap is not None:
            caption_markup = self.finish(self.inline(cap, page, cites), page, cites)
        self.table(rows, header_rows, caption_markup, note)

    # --- whole pages ---------------------------------------------------------

    def page_sources(self, details, page, title="Sources"):
        items = details.find("ol").find_all("li", recursive=False)
        self.story.append(CondPageBreak(40 * mm))
        self.story.append(Rule(TEXT_W, space=10))
        self.story.append(Paragraph(f"{title} for this chapter" if page != "sources.html"
                                    else "Sources for this annex", self.s["srchead"]))
        for n, li in enumerate(items, 1):
            links = li.find_all("a")
            main = links[0]
            label = esc(squash(main.get_text()).strip())
            url = main["href"]
            text = f'<a name="src-{slug(page)}-{n}"/>{label}<br/>'
            text += f'<a href="{esc(url)}" color="{LINK}">{esc(url)}</a>'
            self.anchors.add(f"src-{slug(page)}-{n}")
            for extra in links[1:]:
                if "method-link" in (extra.get("class") or []):
                    target = self.resolve(extra["href"], page)
                    text += (f'<br/><font color="#5b6762">Research note:</font> '
                             f'<a href="{esc(target)}" color="{LINK}">Annex A, '
                             f'{esc(self.note_titles.get(target, "source register"))}</a>')
            self.story.append(Paragraph(text, self.s["src"], bulletText=f"{n}."))

    def figure(self, fig, page, cites, chapter):
        cap = self.finish(self.inline(fig.find("figcaption"), page, cites), page, cites)
        data = fig.find_next_sibling("details", class_="chart-data")
        data["data-used"] = "1"
        table = data.find("table")
        rows = []
        for tr in table.find_all("tr"):
            rows.append([squash(c.get_text()).strip() for c in tr.find_all(["th", "td"])])
        self.fig_no[chapter] = self.fig_no.get(chapter, 0) + 1
        fig_label = f"Figure {chapter}.{self.fig_no[chapter]}"
        annex_no = len(self.figure_tables) + 1
        anchor = f"annexb-{annex_no}"
        self.figure_tables.append((anchor, f"Table B.{annex_no}", fig_label, table, page))
        self.links.append((anchor, None))
        if fig.find("div", class_="multiples"):
            drawing = small_multiples(rows, TEXT_W - NUM_INDENT)
        elif fig.find("div", class_="pair-row"):
            legend = [squash(sp.get_text()).strip() for sp in fig.select("p.legend span")]
            drawing = paired_bars(rows, TEXT_W - NUM_INDENT, legend)
        else:
            drawing = bar_chart(rows, TEXT_W - NUM_INDENT)
        block = [
            Paragraph(self.take_anchors() + f"{fig_label}: {cap}", self.s["caption"]),
            drawing,
            Paragraph(
                f'The figures are listed in <a href="#{anchor}" color="{LINK}">'
                f"Annex B, Table B.{annex_no}</a>.",
                self.s["note"],
            ),
        ]
        self.story.append(Indenter(left=NUM_INDENT))
        self.story.append(KeepTogether(block))
        self.story.append(Indenter(left=-NUM_INDENT))

    def blocks(self, container, page, cites, chapter, numbered=True, h2_level=1, demote=0):
        """Convert the children of a site <main> (or part of it) to flowables."""
        for el in container.children:
            if not isinstance(el, Tag):
                continue
            if el.get("id"):
                self.add_anchor(f"{slug(page)}--{el['id']}")
            name = el.name
            classes = el.get("class") or []
            if name == "nav" or (name == "details" and "page-sources" in classes):
                continue
            if name == "details" and "chart-data" in classes:
                if not el.get("data-used"):
                    raise SystemExit(f"{page}: chart data without a chart")
                continue  # printed in Annex B
            if name == "h1":
                continue
            nxt = el.find_next_sibling()
            if name == "h2" and nxt is not None and "topics" in (nxt.get("class") or []):
                continue  # "The chapters": replaced by the contents page
            if name in ("h2", "h3", "h4"):
                markup = self.finish(self.inline(el, page, cites), page, cites)
                depth = int(name[1]) - 2
                style = self.s["h2"] if depth + demote == 0 else self.s["h3"]
                self.heading(markup, style, h2_level + depth, toc=h2_level + depth <= 1)
            elif name == "p":
                markup = self.finish(self.inline(el, page, cites), page, cites)
                if not markup:
                    continue
                if numbered:
                    self.numbered(markup)
                else:
                    self.story.append(Paragraph(self.take_anchors() + markup, self.s["plain"]))
            elif name in ("ul", "ol"):
                if "topics" in classes:  # list of chapters: replaced by the contents
                    continue
                self.flush_anchors()
                ordered = name == "ol"
                for i, li in enumerate(el.find_all("li", recursive=False), 1):
                    markup = self.finish(self.inline(li, page, cites), page, cites)
                    self.story.append(
                        Paragraph(markup, self.s["bullet"], bulletText=f"{i}." if ordered else "•")
                    )
                self.story.append(Spacer(1, 4))
            elif name == "div" and "table-wrap" in classes:
                self.tab_no[chapter] = self.tab_no.get(chapter, 0) + 1
                table = el.find("table")
                cap = table.find("caption")
                cap_markup = None
                if cap is not None:
                    cap_markup = (f"Table {chapter}.{self.tab_no[chapter]}: "
                                  + self.finish(self.inline(cap, page, cites), page, cites))
                self.html_table(table, page, cites, cap_markup)
            elif name == "table":
                self.html_table(el, page, cites)
            elif name == "figure" and "chart" in classes:
                self.figure(el, page, cites, chapter)
            elif name == "details":
                self.details(el, page, cites, chapter, numbered)
            elif name == "blockquote":
                markup = self.finish(self.inline(el, page, cites), page, cites)
                self.story.append(Paragraph(markup, self.s["bullet"]))
            elif name in ("div", "section"):
                self.blocks(el, page, cites, chapter, numbered, h2_level, demote)
            else:
                raise SystemExit(f"{page}: no rule for <{name} class={classes}>")

    def details(self, el, page, cites, chapter, numbered):
        summary = el.find("summary")
        title = self.finish(self.inline(summary, page, cites), page, cites)
        self.heading(title, self.s["h3"], 2, toc=False)
        for child in el.children:
            if not isinstance(child, Tag) or child.name == "summary":
                continue
            # A paragraph that is only a link prints the address, for readers on paper.
            if child.name == "p" and len(child.find_all(True)) == 1 and child.a is not None \
                    and squash(child.get_text()).strip() == squash(child.a.get_text()).strip():
                label = squash(child.a.get_text()).strip()
                target = self.resolve(child.a["href"], page)
                shown = {"View official source": "Official source",
                         "Read the local source copy": "Archived copy"}.get(label, label)
                if target.startswith("#"):
                    text = f'<a href="{esc(target)}" color="{LINK}">{esc(label)}</a>'
                else:
                    text = (f'<font color="#5b6762">{esc(shown)}:</font> '
                            f'<a href="{esc(target)}" color="{LINK}">{esc(target)}</a>')
                self.story.append(Paragraph(self.take_anchors() + text, self.s["plain"]))
            elif child.name == "ul" and "downloads" in (child.get("class") or []):
                for li in child.find_all("li"):
                    a = li.find("a")
                    target = self.resolve(a["href"], page)
                    text = (f'{esc(squash(a.get_text()).strip())}: '
                            f'<a href="{esc(target)}" color="{LINK}">{esc(target)}</a>')
                    self.story.append(Paragraph(text, self.s["bullet"], bulletText="•"))
            else:
                wrapper = BeautifulSoup("<div></div>", "html.parser").div
                wrapper.append(child.__copy__())
                self.blocks(wrapper, page, cites, chapter, numbered)

    def site_page(self, page, kicker, chapter, about=None):
        soup = BeautifulSoup((ROOT / page).read_text(encoding="utf-8"), "html.parser")
        main = soup.find("main", id="main")
        h1 = squash(main.find("h1").get_text()).strip()
        self.story.append(NextPageTemplate("body"))
        self.story.append(PageBreak())
        self.add_anchor(f"page-{slug(page)}")
        self.story.append(Paragraph(esc(kicker).upper(), self.s["kicker"]))
        title = h1 if kicker.startswith(("Chapter", "Annex")) else kicker
        outline = f"{kicker}. {h1}" if kicker.startswith("Chapter") else (
            f"{kicker}. {h1}" if kicker.startswith("Annex") else kicker)
        self.heading(esc(title), self.s["h1"], 0)
        self.story[-1].outline_text = outline
        cites = None
        if about:
            about()
            # The overview's own title becomes a section of the introduction.
            self.heading(esc(h1), self.s["h2"], 1)
            self.blocks(main, page, cites, chapter, numbered=True, h2_level=2, demote=1)
        else:
            self.blocks(main, page, cites, chapter, numbered=kicker.startswith(("Chapter", "Intro")))
        self.flush_anchors()
        src = main.find("details", class_="page-sources")
        if src is not None:
            self.page_sources(src, page)


# ------------------------------------------------------------------- charts


def fmt(n):
    return f"{n:,}"


def num(text):
    return int(re.sub(r"[^\d]", "", text))


def bar_chart(rows, width):
    """Horizontal bars: rows = [header, [name, value, share], ...]."""
    data = rows[1:]
    row_h, label_w, value_w = 17, 92, 74
    h = row_h * len(data) + 4
    d = Drawing(width, h)
    top = max(num(r[1]) for r in data)
    bar_w = width - label_w - value_w
    for i, r in enumerate(data):
        y = h - (i + 1) * row_h + 4
        d.add(String(0, y + 2.5, r[0], fontName=BODY, fontSize=9.5, fillColor=INK))
        d.add(Rect(label_w, y, bar_w, 10, fillColor=TINT, strokeColor=None))
        d.add(Rect(label_w, y, bar_w * num(r[1]) / top, 10, fillColor=BLUE, strokeColor=None))
        d.add(String(width, y + 2.5, f"{r[1]} · {r[2]}", fontName=BODY + "-Bold",
                     fontSize=9.5, fillColor=INK, textAnchor="end"))
    return d


def small_multiples(rows, width):
    """Line charts on one scale: rows = [[Nationality, 2016..2025], [name, v...], ...]."""
    years = rows[0][1:]
    data = rows[1:]
    cols, gap = 4, 12
    pw = (width - gap * (cols - 1)) / cols
    ph, title_h = 78, 14
    nrows = (len(data) + cols - 1) // cols
    h = nrows * (ph + title_h + 14)
    d = Drawing(width, h)
    ymax = 7000
    for i, r in enumerate(data):
        cx = (i % cols) * (pw + gap)
        top = h - (i // cols) * (ph + title_h + 14)
        d.add(String(cx, top - 11, r[0], fontName=BODY + "-Bold", fontSize=9.5, fillColor=INK))
        ox, oy = cx + 22, top - title_h - ph + 12
        iw, ih = pw - 30, ph - 22
        for v, lab in [(0, "0"), (3500, "3.5k"), (7000, "7k")]:
            yy = oy + ih * v / ymax
            d.add(Line(ox, yy, ox + iw, yy, strokeColor=RULE, strokeWidth=0.4))
            d.add(String(ox - 3, yy - 2.5, lab, fontName=BODY, fontSize=7, fillColor=MUTED,
                         textAnchor="end"))
        vals = [num(v) for v in r[1:]]
        pts = []
        for j, v in enumerate(vals):
            pts += [ox + iw * j / (len(vals) - 1), oy + ih * v / ymax]
        d.add(PolyLine(pts, strokeColor=BLUE, strokeWidth=1.4))
        d.add(Circle(pts[0], pts[1], 1.6, fillColor=BLUE, strokeColor=None))
        d.add(Circle(pts[-2], pts[-1], 2.2, fillColor=BLUE, strokeColor=None))
        d.add(String(pts[-2], pts[-1] + 5, fmt(vals[-1]), fontName=BODY + "-Bold", fontSize=8,
                     fillColor=INK, textAnchor="end"))
        d.add(String(ox, oy - 10, years[0], fontName=BODY, fontSize=7, fillColor=MUTED))
        d.add(String(ox + iw, oy - 10, years[-1], fontName=BODY, fontSize=7, fillColor=MUTED,
                     textAnchor="end"))
    return d


def paired_bars(rows, width, legend):
    """Two bars per row: rows = [header, [name, a, b], ...]."""
    data = rows[1:]
    label_w, value_w = 92, 40
    group_h = 25
    legend_h = 18
    h = legend_h + group_h * len(data)
    d = Drawing(width, h)
    names = legend if len(legend) == 2 and all(legend) else rows[0][1:3]
    x = 0
    for colour, name in zip((BLUE, ORANGE), names):
        d.add(Rect(x, h - 10, 8, 8, fillColor=colour, strokeColor=None))
        d.add(String(x + 12, h - 9, name, fontName=BODY, fontSize=9, fillColor=INK))
        x += 12 + stringWidth(name, BODY, 9) + 18
    top = max(max(num(r[1]), num(r[2])) for r in data)
    bar_w = width - label_w - value_w
    for i, r in enumerate(data):
        y = h - legend_h - (i + 1) * group_h + 4
        d.add(String(0, y + 7, r[0], fontName=BODY, fontSize=9.5, fillColor=INK))
        for k, (colour, v) in enumerate(((BLUE, num(r[1])), (ORANGE, num(r[2])))):
            yy = y + 10 - k * 9
            bw = max(bar_w * v / top, 1)
            d.add(Rect(label_w, yy, bw, 7.5, fillColor=colour, strokeColor=None))
            d.add(String(label_w + bw + 4, yy + 1, fmt(v), fontName=BODY + "-Bold", fontSize=8.5,
                         fillColor=INK))
    return d


# --------------------------------------------------- summary.md (exec summary)


def md_inline(text, b):
    text = esc(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    def repl(m):
        return b.link(html.unescape(m.group(2)), m.group(1), "summary.md")

    # Link targets may contain balanced parentheses, e.g. EPRS_BRI(2025)769502_EN.pdf.
    return re.sub(r"\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)", repl, text)


def summary_md(b, version):
    """Executive summary from summary.md. Lines that only describe the file itself
    (its version and the link to this PDF) are left out."""
    lines = (ROOT / "summary.md").read_text(encoding="utf-8").splitlines()
    blocks, cur = [], []
    for line in lines + [""]:
        if not line.strip():
            if cur:
                blocks.append(cur)
            cur = []
        else:
            cur.append(line)
    for blk in blocks:
        first = blk[0]
        if first.startswith("# "):
            continue
        if first.startswith("## "):
            b.heading(md_inline(first[3:], b), b.s["h2"], 1)
            continue
        if first.startswith("|"):
            rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in blk]
            rows = [r for r in rows if not all(re.fullmatch(r"-+", c) for c in r)]
            b.table([[md_inline(c, b) for c in r] for r in rows], 1)
            continue
        if first.startswith("- "):
            items = []
            for l in blk:
                if l.startswith("- "):
                    items.append(l[2:])
                else:
                    items[-1] += " " + l.strip()
            for it in items:
                b.story.append(Paragraph(md_inline(it, b), b.s["bullet"], bulletText="•"))
            b.story.append(Spacer(1, 4))
            continue
        text = " ".join(l.strip() for l in blk)
        if text.startswith("**Version"):
            # The version is on the cover; the PDF link would point at this document.
            text = re.sub(r"^\*\*Version[^*]+\*\*\s*·\s*", "", text)
            text = re.sub(r"\s*The analysis is also available \[as a PDF\]\([^)]*\)\.", "", text)
            text = text[0].upper() + text[1:]
        if "folder of this repository" in text:
            text = text.replace(
                "Archived copies of the official documents are in the [`research/`](research/) "
                "folder of this repository.",
                "Archived copies of the official documents are listed with each source in "
                "[Annex A](sources.html#source-scheme).",
            )
        # "→ Chapter 1 · source · source" lines are pointers, not paragraphs.
        body, arrow, see = text.partition(" → ")
        b.numbered(md_inline(body, b))
        if arrow:
            b.story.append(Paragraph("→ " + md_inline(see, b), b.s["see"]))


# ------------------------------------------------------------------ document


class Doc(BaseDocTemplate):
    def __init__(self, filename, meta, **kw):
        super().__init__(filename, pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X,
                         topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM, **kw)
        self.meta = meta
        frame = Frame(MARGIN_X, MARGIN_BOTTOM, TEXT_W, PAGE_H - MARGIN_TOP - MARGIN_BOTTOM,
                      id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([
            PageTemplate("cover", [frame], onPage=self.cover_page),
            PageTemplate("body", [frame], onPage=self.body_page),
        ])

    def cover_page(self, c, doc):
        c.saveState()
        c.setFillColor(GREEN)
        c.rect(0, PAGE_H - 9 * mm, PAGE_W, 9 * mm, stroke=0, fill=1)
        c.restoreState()

    def body_page(self, c, doc):
        c.saveState()
        c.setFont(BODY, 8.5)
        c.setFillColor(MUTED)
        c.drawString(MARGIN_X, PAGE_H - 14 * mm, self.meta["running"])
        c.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 14 * mm, self.meta["version_short"])
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.line(MARGIN_X, PAGE_H - 16 * mm, PAGE_W - MARGIN_X, PAGE_H - 16 * mm)
        c.line(MARGIN_X, 16 * mm, PAGE_W - MARGIN_X, 16 * mm)
        c.drawString(MARGIN_X, 12 * mm, self.meta["footer"])
        # Drawn as each page is made, so bookmarks and links keep their own pages.
        total = self.meta.get("total_pages")
        number = f"Page {doc.page} of {total}" if total else f"Page {doc.page}"
        c.drawRightString(PAGE_W - MARGIN_X, 12 * mm, number)
        c.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Heading):
            self.canv.bookmarkPage(flowable.key)
            self.canv.addOutlineEntry(flowable.outline_text, flowable.key,
                                      level=flowable.level, closed=flowable.level >= 1)
            if flowable.toc and flowable.level <= 1:
                self.notify("TOCEntry", (flowable.level, flowable.outline_text, self.page,
                                         flowable.key))


def read_version():
    first = (ROOT / "index.html").read_text(encoding="utf-8")
    footer = re.search(r"<footer>([\s\S]*?)</footer>", first).group(1)
    title = re.search(r"<strong>([^<]+)</strong>", footer).group(1)
    m = re.search(r"Version\s+([\d.]+)\s+·\s+([^·,]+?),?\s+([\d:]+ GMT)?\s*·", squash(footer))
    date = squash(m.group(2)).strip()
    # The PDF's creation date is the version's date, so rebuilding gives the same file.
    when = f"{date} {m.group(3) or '00:00 GMT'}"
    stamp = datetime.strptime(when, "%d %B %Y %H:%M GMT").replace(tzinfo=timezone.utc)
    os.environ.setdefault("SOURCE_DATE_EPOCH", str(int(stamp.timestamp())))
    return title, m.group(1), date


def read_byline():
    """The site footer's description of the analysis and who wrote it, e.g. "A view of the
    September 2026 General Scheme from members of the Russian-speaking community in Ireland."
    """
    first = (ROOT / "index.html").read_text(encoding="utf-8")
    footer = re.search(r"<footer>[\s\S]*?<p>([\s\S]*?)<a ", first).group(1)
    byline = squash(html.unescape(footer)).strip()
    authors = re.search(r" from (.+?)\.$", byline).group(1)
    return byline, authors


def build(output, submitter, total_pages=None):
    styles = make_styles()
    title, version, date = read_version()
    byline, authors = read_byline()
    b = Builder(styles)
    b.fig_no, b.tab_no = {}, {}
    # Every id on every page, so links can be checked as they are made.
    b.known = {"page-summary", "annex-b"}
    for page in PAGE_FILES:
        soup = BeautifulSoup((ROOT / page).read_text(encoding="utf-8"), "html.parser")
        b.known.add(f"page-{slug(page)}")
        for el in soup.find("main").find_all(id=True):
            b.known.add(f"{slug(page)}--{el['id']}")

    # Titles of the research notes, so source lists can name the note they point to.
    src_soup = BeautifulSoup((ROOT / "sources.html").read_text(encoding="utf-8"), "html.parser")
    b.note_titles = {}
    for det in src_soup.find("main").find_all("details"):
        if det.get("id") and det.find("summary"):
            b.note_titles[f"#sources--{det['id']}"] = squash(det.find("summary").get_text()).strip()

    s = styles
    story = b.story

    # Cover.
    story.append(Spacer(1, 18 * mm))
    story.append(Paragraph("SUBMISSION TO THE " + esc(COMMITTEE).upper(), ParagraphStyle(
        "cv0", fontName=BODY + "-Bold", fontSize=10.5, leading=14, textColor=GREEN)))
    story.append(Paragraph(f"Pre-legislative scrutiny of the {esc(SCHEME)}", ParagraphStyle(
        "cv1", fontName=BODY, fontSize=12, leading=16, textColor=INK, spaceAfter=26)))
    story.append(Rule(TEXT_W, GREEN, 1.2, 4))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(esc(title), ParagraphStyle(
        "cv2", fontName=BODY + "-Bold", fontSize=32, leading=37, textColor=INK, spaceAfter=14)))
    story.append(Paragraph(
        esc(byline),
        ParagraphStyle("cv3", fontName=BODY, fontSize=14, leading=19, textColor=MUTED,
                       spaceAfter=22)))
    cover_meta = ParagraphStyle("cv4", fontName=BODY, fontSize=11, leading=16, textColor=INK)
    if submitter:
        story.append(Paragraph(f"<b>Submitted by:</b> {esc(submitter)}", cover_meta))
    story.append(Paragraph(f"<b>Version:</b> {esc(version)}, {esc(date)}", cover_meta))
    story.append(Paragraph(
        f'<b>Online version:</b> <a href="{SITE_URL}" color="{LINK}">{SITE_URL}</a>', cover_meta))
    story.append(Spacer(1, 70 * mm))
    story.append(Paragraph(
        "Paragraphs are numbered continuously from the executive summary to the end of "
        "Chapter 7. Each superscript number refers to the source list at the end of its chapter, "
        "which gives the full address of every publication cited.",
        ParagraphStyle("cv5", fontName=BODY, fontSize=9.5, leading=13, textColor=MUTED)))

    # Contents.
    story.append(NextPageTemplate("body"))
    story.append(PageBreak())
    story.append(Paragraph("Contents", s["h1"]))
    toc = TableOfContents()
    toc.levelStyles = [s["toc0"], s["toc1"]]
    toc.dotsMinLevel = 0
    story.append(toc)

    # Executive summary.
    story.append(PageBreak())
    b.add_anchor("page-summary")
    story.append(Paragraph("EXECUTIVE SUMMARY", s["kicker"]))
    md_title = re.search(r"^# (.+)$", (ROOT / "summary.md").read_text(encoding="utf-8"), re.M)
    b.heading(esc(md_title.group(1).strip()), s["h1"], 0)
    story[-1].outline_text = "Executive summary"
    summary_md(b, version)

    # Introduction, then the chapters and Annex A.
    def about():
        b.heading("About this submission", s["h2"], 1)
        b.numbered(
            f"This is a submission from {esc(authors)} to the {esc(COMMITTEE)} on the "
            f"{esc(SCHEME)}, published on 21 September 2026. It sets out version {esc(version)} "
            f'of the analysis published at <a href="{SITE_URL}" color="{LINK}">{SITE_URL}</a>, '
            "unchanged in substance and arranged as one document."
        )
        b.numbered(
            "The executive summary gives the position in brief. This introduction describes the "
            "proposal and what is still unknown. Chapters 1 to 6 set out the evidence on who "
            "becomes a citizen, the residence period, the language and civics tests, the income "
            "condition, the offence and good-character conditions, and revocation. Chapter 7 "
            "concludes. Annex A records the official sources, data definitions and calculations, "
            "and Annex B lists the figures behind each chart."
        )

    for page, kicker, chapter in PAGES:
        b.site_page(page, kicker, chapter, about if page == "index.html" else None)

    # Annex B: the data behind the charts.
    story.append(PageBreak())
    b.add_anchor("annex-b")
    story.append(Paragraph("ANNEX B", s["kicker"]))
    b.heading("Data for the figures", s["h1"], 0)
    story[-1].outline_text = "Annex B. Data for the figures"
    story.append(Paragraph(
        "The values plotted in each figure, as published on the website’s “Show the data as a "
        "table” views.", s["body"]))
    for anchor, label, fig_label, table, page in b.figure_tables:
        cap = table.find("caption")
        cap_text = esc(squash(cap.get_text()).strip()) if cap is not None else ""
        b.add_anchor(anchor)
        b.html_table(table, page, None, f"{label}: {cap_text} (data for {fig_label})")

    meta = {
        "running": "Submission on the General Scheme of the Irish Nationality and Citizenship "
                   "(Amendment) Bill 2026",
        "version_short": f"Version {version} · {date}",
        "footer": title,
        "total_pages": total_pages,
    }
    doc = Doc(
        str(output), meta,
        title=title,
        author=submitter or authors[0].upper() + authors[1:],
        subject=f"Submission to the {COMMITTEE}: pre-legislative scrutiny of the {SCHEME}",
        keywords=["Irish citizenship", "naturalisation", "pre-legislative scrutiny",
                  "Irish Nationality and Citizenship (Amendment) Bill 2026", "Oireachtas"],
        creator="scripts/build_pdf.py (ReportLab)",
        lang="en-IE",
        displayDocTitle=1,
    )
    doc.multiBuild(story)
    b.pages = doc.page

    missing = sorted({(n, f) for n, f in b.links if n not in b.anchors and n not in
                      {e.key for e in story if isinstance(e, Heading)}})
    if missing:
        raise SystemExit("Unresolved internal links: " + ", ".join(n for n, _ in missing))
    return b


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("output", nargs="?", default=str(ROOT / "citizenship-analysis.pdf"))
    ap.add_argument("--submitter", default=os.environ.get("SUBMITTER", ""))
    ap.add_argument("--fonts", default=os.environ.get("FONT_DIR", ""))
    args = ap.parse_args()
    register_fonts(args.fonts)
    output = Path(args.output).resolve()
    # First pass counts the pages for "Page X of Y"; the second writes the file.
    first = build(output, args.submitter.strip())
    b = build(output, args.submitter.strip(), total_pages=first.pages)
    if b.pages != first.pages:
        raise SystemExit(f"Page count changed between passes: {first.pages} -> {b.pages}")
    print(f"Wrote {args.output}: {b.para_no} numbered paragraphs, "
          f"{len(b.figure_tables)} figures")


if __name__ == "__main__":
    main()
