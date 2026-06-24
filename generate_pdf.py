"""
M&A Intelligence Platform — Architecture PDF
Accenture light theme: white + purple
Run: python generate_pdf.py
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether, NextPageTemplate,
)

W, H   = A4
LM, RM = 20*mm, 20*mm
TM, BM = 22*mm, 20*mm
CW     = W - LM - RM   # 170 mm

# ── Accenture palette ─────────────────────────────────────────────────────────
A_PURPLE    = colors.HexColor("#A100FF")   # Accenture brand purple
A_PURPLE_D  = colors.HexColor("#6900A8")   # darker purple for headers
A_PURPLE_L  = colors.HexColor("#F3E8FF")   # very light purple tint
A_PURPLE_M  = colors.HexColor("#E9D5FF")   # medium light purple
A_BLACK     = colors.HexColor("#1A1A2E")
A_DARKGREY  = colors.HexColor("#374151")
A_MIDGREY   = colors.HexColor("#6B7280")
A_LIGHTGREY = colors.HexColor("#F9FAFB")
A_BORDER    = colors.HexColor("#E5E7EB")
A_WHITE     = colors.white
A_CYAN      = colors.HexColor("#0EA5E9")
A_GREEN     = colors.HexColor("#059669")
A_ORANGE    = colors.HexColor("#D97706")
A_RED       = colors.HexColor("#DC2626")

# ── Styles ────────────────────────────────────────────────────────────────────
def S(name, **kw):
    return ParagraphStyle(name, **kw)

# Cover
sCovTag   = S("ct", fontName="Helvetica-Bold", fontSize=9,  textColor=A_PURPLE_M,  leading=12, letterSpacing=2,  alignment=TA_CENTER)
sCovTitle = S("cT", fontName="Helvetica-Bold", fontSize=34, textColor=A_WHITE,     leading=42, alignment=TA_CENTER)
sCovSub   = S("cS", fontName="Helvetica",      fontSize=15, textColor=A_PURPLE_M,  leading=22, alignment=TA_CENTER)
sCovBody  = S("cB", fontName="Helvetica",      fontSize=10, textColor=colors.HexColor("#C4B5FD"), leading=16, alignment=TA_CENTER)
sCovNote  = S("cN", fontName="Helvetica",      fontSize=8,  textColor=colors.HexColor("#7C3AED"), leading=11, alignment=TA_CENTER)

# Section
sSecTag   = S("stg", fontName="Helvetica-Bold", fontSize=8,  textColor=A_PURPLE,   leading=11, letterSpacing=2)
sSecTitle = S("sti", fontName="Helvetica-Bold", fontSize=20, textColor=A_BLACK,    leading=26, spaceBefore=2, spaceAfter=4)
sSecSub   = S("ssu", fontName="Helvetica",      fontSize=11, textColor=A_MIDGREY,  leading=16, spaceAfter=10)

# Content
sH2    = S("h2",  fontName="Helvetica-Bold", fontSize=12, textColor=A_BLACK,     leading=16, spaceBefore=12, spaceAfter=5)
sH3    = S("h3",  fontName="Helvetica-Bold", fontSize=8,  textColor=A_PURPLE,    leading=12, spaceBefore=6,  spaceAfter=4, letterSpacing=1.5)
sBody  = S("bo",  fontName="Helvetica",      fontSize=10, textColor=A_DARKGREY,  leading=15, spaceBefore=0,  spaceAfter=5)
sBold  = S("bld", fontName="Helvetica-Bold", fontSize=10, textColor=A_BLACK,     leading=15, spaceBefore=4,  spaceAfter=3)
sSmall = S("sm",  fontName="Helvetica",      fontSize=8,  textColor=A_MIDGREY,   leading=12, spaceBefore=0,  spaceAfter=2)
sMono  = S("mn",  fontName="Helvetica-Bold", fontSize=9,  textColor=A_PURPLE_D,  leading=14, spaceBefore=4,  spaceAfter=4)
sTH    = S("th",  fontName="Helvetica-Bold", fontSize=8,  textColor=A_WHITE,     leading=11, letterSpacing=0.5)
sTD    = S("td",  fontName="Helvetica",      fontSize=9,  textColor=A_DARKGREY,  leading=13)
sTDB   = S("tdb", fontName="Helvetica-Bold", fontSize=9,  textColor=A_BLACK,     leading=13)
sStN   = S("stn", fontName="Helvetica-Bold", fontSize=11, textColor=A_WHITE,     leading=14, alignment=TA_CENTER)
sFootL = S("ftl", fontName="Helvetica",      fontSize=8,  textColor=A_MIDGREY,   leading=10)

# Metrics
sMV = S("mv", fontName="Helvetica-Bold", fontSize=24, textColor=A_PURPLE,    leading=30, alignment=TA_CENTER)
sML = S("ml", fontName="Helvetica",      fontSize=8,  textColor=A_MIDGREY,   leading=11, alignment=TA_CENTER)

# ── Utilities ─────────────────────────────────────────────────────────────────
def sp(h=8): return Spacer(1, h)
def HR(c=A_BORDER, t=0.5, b=4, a=10): return HRFlowable(width="100%", thickness=t, color=c, spaceBefore=b, spaceAfter=a)

def sec(tag, title, sub=""):
    out = [sp(4), Paragraph(tag.upper(), sSecTag), Paragraph(title, sSecTitle)]
    if sub: out.append(Paragraph(sub, sSecSub))
    out.append(HR(A_PURPLE, 1.5, 2, 16))
    return out

def card(title, paras, lc=A_PURPLE):
    items = []
    if title:
        items.append(Paragraph(title.upper(), sH3))
    items += paras
    t = Table([[items]], colWidths=[CW])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), A_PURPLE_L),
        ("LEFTPADDING",  (0,0),(-1,-1), 14),
        ("RIGHTPADDING", (0,0),(-1,-1), 14),
        ("TOPPADDING",   (0,0),(-1,-1), 11),
        ("BOTTOMPADDING",(0,0),(-1,-1), 11),
        ("LINEBEFORE",   (0,0),(-1,-1), 3, lc),
        ("BOX",          (0,0),(-1,-1), 0.5, A_PURPLE_M),
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
    ]))
    return t

def dtable(headers, rows, cws):
    hrow = [Paragraph(h, sTH) for h in headers]
    drows = [[Paragraph(str(c), sTD) for c in row] for row in rows]
    t = Table([hrow] + drows, colWidths=cws)
    ts = [
        ("BACKGROUND",   (0,0),(-1,0),  A_PURPLE_D),
        ("TOPPADDING",   (0,0),(-1,-1), 7),
        ("BOTTOMPADDING",(0,0),(-1,-1), 7),
        ("LEFTPADDING",  (0,0),(-1,-1), 9),
        ("RIGHTPADDING", (0,0),(-1,-1), 9),
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("GRID",         (0,0),(-1,-1), 0.4, A_BORDER),
        ("LINEBELOW",    (0,0),(-1,0),  1.5, A_PURPLE),
    ]
    for i in range(1, len(drows)+1):
        ts.append(("BACKGROUND", (0,i),(-1,i), A_WHITE if i%2==1 else A_LIGHTGREY))
    t.setStyle(TableStyle(ts))
    return t

def step(num, col, title, body):
    badge = Table([[Paragraph(str(num), sStN)]], colWidths=[7*mm], rowHeights=[7*mm])
    badge.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), col),
        ("TOPPADDING",   (0,0),(-1,-1), 0),
        ("BOTTOMPADDING",(0,0),(-1,-1), 0),
        ("LEFTPADDING",  (0,0),(-1,-1), 0),
        ("RIGHTPADDING", (0,0),(-1,-1), 0),
        ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
    ]))
    content = [Paragraph(f"<b>{title}</b>", sBold), Paragraph(body, sBody)]
    row = Table([[badge, content]], colWidths=[11*mm, CW-11*mm])
    row.setStyle(TableStyle([
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0),(0,-1), 0),
        ("RIGHTPADDING", (0,0),(0,-1), 8),
        ("LEFTPADDING",  (1,0),(1,-1), 0),
        ("TOPPADDING",   (0,0),(-1,-1), 0),
        ("BOTTOMPADDING",(0,0),(-1,-1), 0),
    ]))
    return row

def layer(label, sub, col, items):
    t = Table([
        [Paragraph(f"<b>{label}</b>   <font color='#ffffff' size='8'>{sub}</font>",
                   S("lh", fontName="Helvetica-Bold", fontSize=9, textColor=A_WHITE, leading=13))],
        [Paragraph("   |   ".join(items), sSmall)],
    ], colWidths=[CW])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(0,0), col),
        ("BACKGROUND",   (0,1),(0,1), A_PURPLE_L),
        ("LEFTPADDING",  (0,0),(-1,-1), 12),
        ("RIGHTPADDING", (0,0),(-1,-1), 12),
        ("TOPPADDING",   (0,0),(0,0), 8),
        ("BOTTOMPADDING",(0,0),(0,0), 8),
        ("TOPPADDING",   (0,1),(0,1), 7),
        ("BOTTOMPADDING",(0,1),(0,1), 8),
        ("LINEBEFORE",   (0,0),(-1,-1), 3, col),
        ("BOX",          (0,0),(-1,-1), 0.5, A_BORDER),
    ]))
    return t

# ── Page templates ────────────────────────────────────────────────────────────
def cover_bg(cv, doc):
    cv.saveState()
    # Solid deep purple background
    cv.setFillColor(A_PURPLE_D)
    cv.rect(0, 0, W, H, fill=1, stroke=0)
    # Accent stripe bottom
    cv.setFillColor(A_PURPLE)
    cv.rect(0, 0, W, 8, fill=1, stroke=0)
    # Right side decorative bar
    cv.setFillColor(colors.HexColor("#7C00CC"))
    cv.rect(W-10, 0, 10, H, fill=1, stroke=0)
    cv.restoreState()

def body_page(cv, doc):
    cv.saveState()
    cv.setFillColor(A_WHITE)
    cv.rect(0, 0, W, H, fill=1, stroke=0)
    # Top purple bar
    cv.setFillColor(A_PURPLE)
    cv.rect(0, H-4, W, 4, fill=1, stroke=0)
    # Left accent stripe
    cv.setFillColor(A_PURPLE_L)
    cv.rect(0, 0, 4, H, fill=1, stroke=0)
    # Footer line
    cv.setStrokeColor(A_BORDER)
    cv.setLineWidth(0.5)
    cv.line(LM, BM-5*mm, W-RM, BM-5*mm)
    # Footer text
    cv.setFont("Helvetica", 8)
    cv.setFillColor(A_MIDGREY)
    cv.drawString(LM, BM-8*mm, "Accenture V&A  ·  M&A Intelligence Platform  ·  Architecture & Orchestration  ·  2025")
    cv.drawRightString(W-RM, BM-8*mm, f"Page {doc.page}")
    cv.restoreState()

# ── Document ──────────────────────────────────────────────────────────────────
cover_f = Frame(LM, BM, W-LM-RM, H-TM-BM, id="cover")
body_f  = Frame(LM, BM+6*mm, W-LM-RM, H-TM-BM-6*mm, id="body")
doc = BaseDocTemplate(
    "MA_Intelligence_Platform_Architecture.pdf",
    pagesize=A4,
    title="M&A Intelligence Platform — Architecture & Orchestration",
    author="Accenture V&A",
)
doc.addPageTemplates([
    PageTemplate(id="Cover", frames=[cover_f], onPage=cover_bg),
    PageTemplate(id="Body",  frames=[body_f],  onPage=body_page),
])

story = []

# ════════════════════════════════════════
# COVER
# ════════════════════════════════════════
story += [
    sp(44),
    Paragraph("ACCENTURE  V&amp;A  PRACTICE", sCovTag),
    sp(16),
    Paragraph("M&amp;A Intelligence Platform", sCovTitle),
    sp(12),
    Paragraph("Architecture &amp; Orchestration", sCovSub),
    sp(8),
    HRFlowable(width="45%", thickness=2, color=A_PURPLE, spaceBefore=2, spaceAfter=22, hAlign="CENTER"),
    Paragraph("Prototype  ·  2025", sCovBody),
    sp(46),
]

# Cover metrics
mc = (W-LM-RM)/5
mt = Table(
    [[Paragraph(v, sMV) for v in ["2","9","6","11","0"]],
     [Paragraph(l, sML) for l in ["Modes","Agents","Data Sources","Report Sections","Cloud Deps*"]]],
    colWidths=[mc]*5
)
mt.setStyle(TableStyle([
    ("BACKGROUND",   (0,0),(-1,-1), colors.HexColor("#3B006B")),
    ("BOX",          (0,0),(-1,-1), 0.5, colors.HexColor("#7C00CC")),
    ("INNERGRID",    (0,0),(-1,-1), 0.5, colors.HexColor("#5A009A")),
    ("TOPPADDING",   (0,0),(-1,-1), 10),
    ("BOTTOMPADDING",(0,0),(-1,-1), 10),
    ("ALIGN",        (0,0),(-1,-1), "CENTER"),
    ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
]))
story += [
    mt, sp(32),
    Paragraph(
        "A local multi-agent system that turns a company name into an 11-section intelligence dossier, "
        "or an investment thesis into a list of acquisition targets with quantified synergies — "
        "grounded in real scraped data. All analysis runs locally via Ollama. "
        "Data enrichment optionally uses OpenAI, Grok, or Gemini.",
        sCovBody),
    sp(8),
    Paragraph("* OpenAI / Grok / Gemini are optional data enrichment only — not required for core operation.", sCovNote),
    NextPageTemplate("Body"), PageBreak(),
]

# ════════════════════════════════════════
# 01 · OVERVIEW
# ════════════════════════════════════════
story += sec("01 · Overview", "Platform Overview",
    "Two modes of operation on a shared data ingestion and agent processing foundation.")
story += [
    Paragraph("Mode 1 — Intelligence Profile", sH2),
    Paragraph(
        "The user enters a company name or URL. The platform runs Phase 0 data ingestion across 6 sources, "
        "then routes the assembled context through 9 specialist agents. Agents 1–2 run sequentially to establish "
        "company identity and services. Agents 3–8 run in parallel for locations, clients, financials, leadership, "
        "Glassdoor, and workforce. Agent 9 runs last with all prior outputs to produce strategic intelligence. "
        "The final report contains 11 structured sections.", sBody),
    sp(4),
    Paragraph("Mode 2 — M&A Discovery", sH2),
    Paragraph(
        "The user enters an acquirer and investment thesis: sector, geography, capability gap, revenue range. "
        "The platform profiles the acquirer via Phase 0 and an acquirer profile agent, then identifies up to 5 "
        "real acquisition targets using a cloud LLM call (OpenAI, Grok, or Gemini — whichever key is set) or a "
        "DuckDuckGo fallback. Each target is independently profiled and a synergy model agent produces quantified "
        "USD synergy figures and a deal valuation range per target.", sBody),
    sp(8),
    card("Grounding Principle — No Hallucination by Design", [
        Paragraph(
            "Every agent operates on real scraped data passed as context — not on the model's training recall. "
            "Phase 0 always runs before any Ollama agent. Agents output 'Not found in allowed sources' for any "
            "field not evidenced in the provided context. No agent queries the internet directly.", sBody),
    ]),
    PageBreak(),
]

# ════════════════════════════════════════
# 02 · SYSTEM ARCHITECTURE
# ════════════════════════════════════════
story += sec("02 · System Architecture", "Five-Layer Stack",
    "Request flows top-down from browser to Ollama. Response assembles bottom-up through the same layers.")
for lbl, sub, col, items in [
    ("Layer 1 · Presentation", "Browser — index.html · app.js · index.css", A_PURPLE,
     ["Single-page app (two modes)", "Live progress polling", "11-section report renderer",
      "Synergy model display", "Project history sidebar", "Data source chips"]),
    ("Layer 2 · API", "FastAPI — main.py — port 8083", A_CYAN,
     ["POST /api/analyze", "POST /api/discover", "GET /api/status/:id",
      "GET /api/report/:id", "GET /api/projects", "DELETE /api/projects/:id"]),
    ("Layer 3 · Orchestration", "orchestrator.py — background threads", A_ORANGE,
     ["Task manager (UUID dict)", "Profile pipeline", "Discovery pipeline",
      "ThreadPoolExecutor for parallel agents", "Progress logger", "JSON persistence"]),
    ("Layer 4 · Data Ingestion", "scraper.py + llm_research.py — Phase 0", A_GREEN,
     ["Wikipedia REST API", "DDG Instant Answer", "Website scrape (httpx + BS4)",
      "DDG web + news search", "yFinance financials", "OpenAI / Grok / Gemini (optional)"]),
    ("Layer 5 · LLM Processing", "agents.py — Ollama llama3.2 @ localhost:11434", A_RED,
     ["9 profile agents", "3 discovery agents", "Pydantic-validated JSON output",
      "Context injection per agent", "180 s timeout per call"]),
]:
    story += [layer(lbl, sub, col, items), sp(5)]
story.append(PageBreak())

# ════════════════════════════════════════
# 03 · USER INPUT
# ════════════════════════════════════════
story += sec("03 · Stage 1 — User Input", "What the User Provides",
    "Two forms. Submitting creates a background task immediately and returns a task_id for polling.")
story += [
    Paragraph("Intelligence Profile — Fields", sH2),
    dtable(["Field","Required","Description"],
        [["Company Name / URL","Yes","Full company name or official website URL. Used as the primary key across all 6 Phase 0 sources."],
         ["Ollama Model","No","Defaults to llama3.2:latest. Any locally pulled Ollama model is accepted."],
         ["Simulation Mode","No","Loads a pre-built Avanade profile. No Ollama or internet needed. For demos."]],
        [48*mm, 18*mm, CW-66*mm]),
    sp(10),
    Paragraph("M&A Discovery — Fields", sH2),
    dtable(["Field","Required","Description"],
        [["Acquirer Name","Yes","Company seeking acquisitions. Fully profiled via Phase 0 before discovery begins."],
         ["Sector","No","Target industry — e.g. IT Services, BPO, Cloud Native."],
         ["Geography","No","Target region — e.g. India, Southeast Asia, UK."],
         ["Capability Gap","No","What the acquirer lacks — e.g. AI/ML, SAP, Salesforce."],
         ["Revenue Range","No","Target size filter — e.g. $50M–$500M. Passed to the discovery LLM prompt."],
         ["Simulation Mode","No","Loads a pre-built result. No Ollama or internet needed. For demos."]],
        [38*mm, 18*mm, CW-56*mm]),
    sp(10),
    card("Task Lifecycle After Submit", [
        Paragraph("1.  Browser POSTs payload to /api/analyze or /api/discover.", sBody),
        Paragraph("2.  FastAPI validates via Pydantic, creates a UUID task, stores it in the in-memory tasks dict, returns task_id immediately.", sBody),
        Paragraph("3.  The pipeline runs in a daemon background thread — the HTTP response returns before processing begins.", sBody),
        Paragraph("4.  Browser polls GET /api/status/:id every 2 seconds, receiving progress percentage, current agent name, and running log.", sBody),
        Paragraph("5.  On status = 'completed', browser fetches GET /api/report/:id and renders the full report.", sBody),
    ]),
    PageBreak(),
]

# ════════════════════════════════════════
# 04 · DATA INGESTION
# ════════════════════════════════════════
story += sec("04 · Stage 2 — Data Ingestion", "Phase 0 Pipeline",
    "Six sources queried in sequence before any agent runs. Outputs assembled into one prioritised context string.")
for num, col, title, body in [
    (1, A_GREEN,    "Wikipedia REST API",
     "Calls en.wikipedia.org/api/rest_v1/page/summary/{company}. Free, no auth, no rate limit. Returns a "
     "structured extract with company description, HQ, founding year, and key facts. Always attempted first."),
    (2, A_GREEN,    "DuckDuckGo Instant Answer API",
     "Calls api.duckduckgo.com/?q={company}&format=json. Returns a structured infobox with HQ, revenue, "
     "employee count, and website when a matching entity exists. Adds machine-readable facts to complement Wikipedia."),
    (3, A_CYAN,     "Official Website Scrape",
     "Uses httpx to fetch up to 3 pages (homepage, /about, /services) from the company's official domain. "
     "BeautifulSoup4 strips boilerplate and retains body text. Captures self-described service language and "
     "proprietary product names absent from public indexes."),
    (4, A_CYAN,     "DuckDuckGo Web + News Search",
     "DDGS library runs two searches — broad web facts and recent news. Returns ranked text snippets from "
     "multiple external sources. A 2-second delay respects DDG rate limits. Captures analyst commentary, "
     "press releases, and third-party assessments not on the company's own site."),
    (5, A_ORANGE,   "yFinance — Public Company Financials",
     "Ticker lookup via yf.Search(), then yf.Ticker() pulls annual revenue, gross profit, operating income, "
     "market cap, and enterprise value. Public companies only. Most authoritative financial source in context."),
    (6, A_PURPLE,   "OpenAI / Grok / Gemini — Optional LLM Enrichment",
     "When a key is set in config.py, one minimal call (~60 tokens in, max 400 out) requests 9 structured JSON "
     "fields: HQ, founded, employees, revenue, sector, services, clients, executives, news. "
     "Priority order: OpenAI → Grok → Gemini (first available key wins). "
     "Output placed FIRST in the assembled context — highest priority source."),
]:
    story += [KeepTogether([step(num, col, title, body), sp(8)])]

story += [
    sp(4),
    card("Context Assembly — Priority Order", [
        Paragraph("After all 6 sources run, build_full_context() assembles one string in this order:", sBold),
        Paragraph("[LLM Research]  →  [Wikipedia]  →  [DDG Instant]  →  [Website pages]  →  [DDG snippets]  →  [yFinance]", sMono),
        Paragraph("This string is the only input every Ollama agent receives. No agent calls the internet directly.", sBody),
    ]),
    PageBreak(),
]

# ════════════════════════════════════════
# 05 · PROFILE PROCESSING
# ════════════════════════════════════════
story += sec("05 · Stage 3 / Mode 1 — Intelligence Profile", "Agent Processing",
    "9 agents. Sequential (1–2) → Parallel (3–8) → Sequential (9). All agents receive the Phase 0 context string.")
for num, col, title, body in [
    (1, A_ORANGE, "Agent 1 — Company Overview",
     "Extracts: legal name, company type (public/private/JV), founded year, HQ, global office count, employee count, "
     "sector, business model, certifications, website and LinkedIn URLs. "
     "Schema: CompanyOverviewOutput (12 typed fields). Forms the report header."),
    (2, A_ORANGE, "Agent 2 — Services & Products",
     "Lists named service lines and products, each with a description drawn from context. "
     "Schema: ServicesOutput — list of ServiceItem {name, description}. Structured for cross-company comparison."),
]:
    story += [KeepTogether([step(num, col, title, body), sp(8)])]

story += [sp(4), Paragraph("Agents 3–8 — Parallel Execution via ThreadPoolExecutor", sH2),
    dtable(["Agent","Name","What it extracts"],
        [["3","Locations & Offices","HQ address, AMER/EMEA/APAC office lists, delivery centres, parent/subsidiary entities"],
         ["4","Clients & Verticals","Named client accounts, industry verticals served, case study references"],
         ["5","Financials & Revenue","Revenue figures, YoY growth, gross margin, funding history, data source note"],
         ["6","Leadership Team","C-suite names, titles, years in role, board members where mentioned"],
         ["7","Glassdoor & News","Employee rating, top pros and cons, recent news headlines and dates"],
         ["8","Workforce & Culture","Headcount by region, hiring trends, stated culture and DEI posture"]],
        [12*mm, 38*mm, CW-50*mm]),
    sp(10),
    KeepTogether([step(9, A_RED, "Agent 9 — Strategic Intelligence",
        "Runs after all 8 agents complete. Receives Phase 0 context PLUS all prior agent outputs. Produces: "
        "competitive positioning, M&A history, partnerships, technology bets, strategic risks, and M&A attractiveness "
        "summary with deal rationale. Primary deliverable for deal teams."), sp(4)]),
    PageBreak(),
]

# ════════════════════════════════════════
# 06 · DISCOVERY PROCESSING
# ════════════════════════════════════════
story += sec("06 · Stage 3 / Mode 2 — M&A Discovery", "Pipeline Processing",
    "4 stages. LLM-first target identification (OpenAI → Grok → Gemini fallback chain). Each target fully profiled before synergy modelling.")
for num, col, title, body in [
    (1, A_GREEN, "Stage 1 — Acquirer Profile",
     "Full Phase 0 data ingestion runs on the acquirer. Acquirer profile agent extracts: current capability set, "
     "M&A acquisition history, strategic priorities, technology gaps, and market position. "
     "This output shapes the discovery prompt and is later combined with each target profile for synergy modelling."),
    (2, A_CYAN, "Stage 2 — Target Discovery (LLM-First with DDG Fallback)",
     "PRIMARY PATH: When any key is set (OpenAI → Grok → Gemini, first available), one minimal LLM call sends "
     "the investment thesis and requests up to 5 real company names. Model instructed to name only companies "
     "it is confident exist — eliminates hallucination risk entirely.\n\n"
     "FALLBACK PATH: DDG web search runs on thesis keywords → raw snippets → Ollama extract-targets agent → "
     "validation filter (length >2, not 'company*', not numeric). Pipeline aborts if DDG returns no snippets "
     "rather than proceeding with fabricated names."),
    (3, A_ORANGE, "Stage 3 — Per-Target Profiling",
     "For each of up to 5 targets, the full Phase 0 pipeline runs independently: Wikipedia, DDG Instant, "
     "website scrape, DDG search, yFinance, optional LLM enrichment. A subset of profile agents then runs "
     "(overview, services, locations, financials) to produce a grounded target dossier."),
    (4, A_RED, "Stage 4 — Synergy Model (Per Target)",
     "Agent receives acquirer profile + target profile as combined context. Produces SynergyModelOutput — "
     "12 typed numeric USD fields. Revenue synergies: cross-sell potential, geographic expansion uplift, "
     "new service revenue. Cost synergies: headcount rationalisation, infrastructure consolidation, procurement. "
     "Capability synergies: IP value, new verticals, certifications. Deal metrics: low/high range (USD), "
     "integration risk score (1–10), strategic fit score (1–10)."),
]:
    story += [KeepTogether([step(num, col, title, body.replace("\n\n","<br/><br/>")), sp(10)])]
story.append(PageBreak())

# ════════════════════════════════════════
# 07 · OUTPUT
# ════════════════════════════════════════
story += sec("07 · Stage 4 — Output", "Report Structure & Delivery",
    "Assembled into one JSON document per run. Stored in projects/. Rendered on demand in the browser.")
story += [
    Paragraph("Intelligence Profile — 11 Sections", sH2),
    dtable(["Section","Content"],
        [["§1  Business Overview","High-level summary, company type, business model"],
         ["§2  Company Overview","Legal name, HQ, founded, employee count, certifications, URLs"],
         ["§3  Services & Products","Named service lines with descriptions — structured for comparison"],
         ["§4  Locations","HQ, AMER/EMEA/APAC offices, delivery centres"],
         ["§5  Clients","Named accounts, industry verticals, case study references"],
         ["§6  Financials","Revenue, YoY growth, gross margin, funding, data source note"],
         ["§7  Leadership","C-suite names, titles, tenure; board members"],
         ["§8  Glassdoor & Sentiment","Employee rating, top pros and cons"],
         ["§9  News","Recent headlines and dates"],
         ["§10 Workforce & Culture","Headcount by region, hiring trends, culture, DEI"],
         ["§11 Strategic Intelligence","Competitive positioning, M&A history, risks, attractiveness summary"]],
        [48*mm, CW-48*mm]),
    sp(10),
    Paragraph("M&A Discovery — Per-Target Report", sH2),
    dtable(["Tab","Content"],
        [["Overview","Profile summary: HQ, sector, employees, revenue, business model"],
         ["Services","Target's service lines and product portfolio"],
         ["Financials","Revenue, growth, funding or public market data"],
         ["Synergy Model","12 USD fields: revenue/cost/capability synergies, deal range, risk score, fit score"]],
        [32*mm, CW-32*mm]),
    sp(10),
    card("Persistence & Delivery", [
        Paragraph(
            "Reports saved as projects/{task_id}.json on completion — persist across server restarts. "
            "Source chips in the report header show which data sources were active: "
            "Website · Wikipedia · DDG · yFinance · OpenAI · Grok · Gemini. "
            "Live progress streams during processing: each agent logs its completion percentage.", sBody),
    ]),
    PageBreak(),
]

# ════════════════════════════════════════
# 08 · AGENT REGISTRY
# ════════════════════════════════════════
story += sec("08 · Agent Registry", "All 12 Agents",
    "Defined in agents.py. Each agent receives the Phase 0 context string prepended to its specialist prompt.")
story += [
    dtable(["ID","Function","Output Schema","Mode","Execution"],
        [["1","agent_company_overview","CompanyOverviewOutput — 12 typed fields: name, type, founded, HQ, employees, sector, model, certs, URLs","Profile","Sequential"],
         ["2","agent_services","ServicesOutput — list of ServiceItem {name, description}","Profile","Sequential"],
         ["3","agent_locations","LocationsOutput — HQ, AMER/EMEA/APAC lists, delivery centres, parent entity","Profile","Parallel"],
         ["4","agent_clients","ClientsOutput — named clients list, verticals list","Profile","Parallel"],
         ["5","agent_financials","FinancialsOutput — revenue, growth %, margin, funding, source note","Profile","Parallel"],
         ["6","agent_leadership","LeadershipOutput — list of Executive {name, title, tenure}","Profile","Parallel"],
         ["7","agent_glassdoor_news","GlassdoorNewsOutput — rating, pros, cons, headlines list","Profile","Parallel"],
         ["8","agent_workforce","WorkforceOutput — headcount by region, hiring trend, culture","Profile","Parallel"],
         ["9","agent_strategic","StrategicOutput — positioning, M&A history, partnerships, risks, attractiveness","Profile","Sequential (last)"],
         ["D1","agent_acquirer_profile","AcquirerProfileOutput — capabilities, gaps, M&A history, priorities","Discovery","Sequential"],
         ["D2","agent_extract_targets","TargetListOutput — list of company name strings (DDG fallback only)","Discovery","Sequential"],
         ["D3","agent_synergy_model","SynergyModelOutput — 12 typed numeric USD fields","Discovery","Per-target"]],
        [10*mm, 44*mm, 70*mm, 22*mm, 24*mm]),
    PageBreak(),
]

# ════════════════════════════════════════
# 09 · TECH STACK
# ════════════════════════════════════════
story += sec("09 · Technology", "Core Technology Stack",
    "Local-first. No cloud services required for core analysis. All LLM inference runs on-device via Ollama.")
story += [
    dtable(["Category","Technology","Purpose"],
        [["Backend","Python 3.11+","Application runtime"],
         ["Backend","FastAPI","REST API framework — routing, validation, static file serving"],
         ["Backend","uvicorn","ASGI server with hot-reload for development"],
         ["Backend","Pydantic v2","Typed data validation and JSON schema generation for all agent outputs"],
         ["Local LLM","Ollama","On-device LLM runtime — serves llama3.2 at localhost:11434"],
         ["Local LLM","llama3.2:latest","Default model for all 12 analysis agents (configurable)"],
         ["Data Ingestion","httpx","Async HTTP client for website scraping"],
         ["Data Ingestion","BeautifulSoup4","HTML parsing and clean text extraction"],
         ["Data Ingestion","ddgs","DuckDuckGo web and news search"],
         ["Data Ingestion","yfinance","Public company financials — revenue, market cap, enterprise value"],
         ["Data Ingestion","Wikipedia REST API","Free structured company summaries — no auth required"],
         ["LLM Enrichment","openai","Optional — GPT-4o-mini for Phase 0 data enrichment"],
         ["LLM Enrichment","google-genai","Optional — Gemini 2.0 Flash as enrichment fallback"],
         ["LLM Enrichment","openai (xAI base URL)","Optional — Grok 3 Mini via xAI API (OpenAI-compatible)"],
         ["Frontend","Vanilla JS + HTML5/CSS3","Single-page app — no framework, no build toolchain"],
         ["Concurrency","threading + ThreadPoolExecutor","Background pipeline + parallel agent invocation"],
         ["Storage","JSON files (projects/)","Report persistence — one file per task"],
         ["Config","config.py","API key storage — local only, never transmitted"]],
        [30*mm, 44*mm, CW-74*mm]),
    PageBreak(),
]

# ════════════════════════════════════════
# 10 · DESIGN DECISIONS
# ════════════════════════════════════════
story += sec("10 · Design Rationale", "Key Design Decisions",
    "Five decisions made during prototyping, each addressing a specific failure mode observed in early builds.")
for col, title, body in [
    (A_GREEN,    "1.  Grounding Before Generation — Data-First Architecture",
     "Problem: Early builds passed only a company name to Ollama agents. The model invented plausible but fabricated "
     "facts: non-existent office locations, made-up revenue figures, invented client names.\n\n"
     "Solution: Phase 0 runs 6 real data sources before any agent is invoked. Agents receive real scraped content as "
     "context and are explicitly forbidden, via the system prompt, from producing facts not present in that context. "
     "Fields without evidence output 'Not found in allowed sources'. The agent role shifts from recall to extraction."),
    (A_PURPLE,   "2.  Local LLM for Analysis — Cloud LLM for Data Enrichment Only",
     "Decision: All 9 analytical agents use Ollama locally — no data leaves the machine, no API cost per run. "
     "OpenAI, Grok, and Gemini are used only in Phase 0 for data enrichment (one call per company) with a priority "
     "chain: OpenAI → Grok → Gemini.\n\n"
     "Implication: The platform works fully offline with zero API keys. Quality degrades gracefully — "
     "Wikipedia, DDG, website scrape, and yFinance alone produce a useful report."),
    (A_CYAN,     "3.  Parallel Agents 3–8 via ThreadPoolExecutor",
     "Problem: Running 9 agents sequentially at 60–90 seconds each would take 10+ minutes per report.\n\n"
     "Solution: Agents 3–8 have no inter-dependencies — each only requires the Phase 0 context string. "
     "They run concurrently via ThreadPoolExecutor. Agent 9 waits for all 6 via as_completed() "
     "before running, receiving the combined outputs of all prior agents as additional context."),
    (A_RED,      "4.  LLM-First Discovery to Prevent Hallucinated Target Names",
     "Problem: When DDG returned sparse results, the Ollama extract-targets agent invented non-existent company "
     "names ('Aerofex', 'Apexion', 'Cirro'). These passed format validation and produced useless synergy models.\n\n"
     "Solution: When any API key is set, OpenAI/Grok/Gemini returns real company names. Ollama is never asked to "
     "discover targets from scratch. The DDG fallback has a validation filter and aborts rather than hallucinating "
     "if no snippets are returned."),
    (A_ORANGE,   "5.  Pydantic Schema Inlining for Ollama Structured Output",
     "Problem: Ollama's format parameter rejects JSON schemas with $ref or $defs — which Pydantic v2 generates "
     "by default for nested models. Unresolved $ref caused Ollama to return unstructured text or refuse to respond.\n\n"
     "Solution: _inline_schema() recursively resolves all $ref references before any schema is passed to Ollama. "
     "This enables complex nested schemas (SynergyModelOutput with 12 typed USD fields, ServicesOutput with a list "
     "of ServiceItem objects) to be enforced reliably across all 12 agents."),
]:
    story += [
        KeepTogether([
            card(None, [
                Paragraph(title, sBold),
                sp(4),
                Paragraph(body.replace("\n\n", "<br/><br/>"), sBody),
            ], lc=col),
            sp(10),
        ])
    ]

doc.build(story)
print("Done: MA_Intelligence_Platform_Architecture.pdf")
