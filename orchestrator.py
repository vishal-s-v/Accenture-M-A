import re
import uuid
import threading
import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any, List

from agents import (
    OLLAMA_MODEL,
    agent_company_overview, agent_services, agent_locations, agent_clients,
    agent_financials, agent_leadership, agent_glassdoor_news, agent_workforce,
    agent_strategic, agent_acquirer_profile, agent_extract_targets, agent_synergy_model,
)
from scraper import gather_company_intelligence, discover_acquisition_targets

tasks: Dict[str, Any] = {}

# Strings that must NOT appear in a target company name
_INVALID_TARGET_TOKENS = frozenset({
    "not found", "allowed sources", "unknown", "n/a", "none", "null",
    "not available", "not disclosed", "tbd", "company name", "example",
})

def _is_valid_target(name: str) -> bool:
    low = name.lower().strip()
    if len(low) <= 2:
        return False
    if re.match(r"^\d", low):
        return False
    if low.startswith("company"):
        return False
    if any(tok in low for tok in _INVALID_TARGET_TOKENS):
        return False
    return True

# ── Simulate data ─────────────────────────────────────────────────────────────
SIMULATE_PROFILE = {
    "company": "Avanade Inc.",
    "overview": {
        "business_overview": "Avanade is a joint venture between Accenture and Microsoft providing IT services primarily on the Microsoft technology platform. The company employs approximately 60,000 professionals across 26 countries. Revenue is estimated at USD 3.5B for FY2023 per PitchBook. Business is concentrated in enterprise Microsoft Cloud, Security, Modern Workplace, and Business Applications.",
        "legal_name": "Avanade Inc.", "company_type": "Joint Venture (Accenture 60%, Microsoft 40%)",
        "year_founded": "2000", "hq": "Seattle, Washington, USA",
        "global_offices": "AMER: USA (8), Canada (2), Brazil (1) | EMEA: UK (3), Germany (2), France (2) | APAC: Australia (2), Japan (2), India (3), Singapore (1)",
        "employee_count": "59,000 (LinkedIn, Q1 2025)", "sector_industry": "Information Technology Services — Microsoft Ecosystem",
        "business_model": "Professional services on time-and-materials and fixed-fee basis for Microsoft platform implementations",
        "certifications_awards": ["Microsoft Solutions Partner (all 6 solution areas)", "ISO 27001", "SOC 2 Type II"],
        "website_url": "https://www.avanade.com", "linkedin_url": "https://www.linkedin.com/company/avanade",
    },
    "services": {"services_solutions_products": [
        {"name": "Azure Infrastructure & Cloud", "description": "Cloud migration, architecture, and infrastructure management on Microsoft Azure"},
        {"name": "Business Applications", "description": "Microsoft Dynamics 365 implementation, customization, and managed support"},
        {"name": "Modern Workplace", "description": "Microsoft 365 deployment, adoption programs, and endpoint management"},
        {"name": "Data & AI", "description": "Data platform engineering, analytics, and Azure AI services delivery"},
        {"name": "Security", "description": "Microsoft Sentinel, Defender, and Entra deployment and managed security"},
        {"name": "Application Innovation", "description": "Custom application development on Azure and Microsoft development stack"},
    ]},
    "locations": {
        "headquarters": "Seattle, Washington, USA",
        "amer_offices": ["New York, NY", "Chicago, IL", "Atlanta, GA", "Dallas, TX", "San Francisco, CA", "Toronto, Canada", "São Paulo, Brazil"],
        "emea_offices": ["London, UK", "Manchester, UK", "Munich, Germany", "Paris, France", "Amsterdam, Netherlands"],
        "apac_offices": ["Sydney, Australia", "Melbourne, Australia", "Tokyo, Japan", "Bangalore, India", "Singapore"],
        "delivery_centers": ["Bangalore, India (offshore)", "Manila, Philippines (offshore)", "Monterrey, Mexico (nearshore)"],
        "parent_company": "Joint venture: Accenture (60%) and Microsoft (40%)",
    },
    "clients": {
        "named_clients": ["Shell", "Unilever", "Nestlé", "Allianz", "Vodafone"],
        "client_segments": ["Financial Services", "Energy", "Consumer Goods", "Public Sector", "Healthcare"],
        "anonymous_case_studies": "Referenced",
    },
    "financials": {
        "revenue": "USD 3.5B (FY2023, PitchBook)", "revenue_source": "PitchBook",
        "revenue_per_employee": "USD 59K",
        "funding_rounds": [],
        "acquisitions": [{"company_name": "Fellowmind", "descriptor": "Microsoft partner Nordics and DACH", "year": "2023", "deal_value": "Not disclosed", "headcount_added": "~1,800", "strategic_rationale": "Expand Microsoft Dynamics presence in Northern Europe"}],
        "key_partnerships": ["Microsoft", "SAP", "Salesforce", "ServiceNow", "UiPath"],
    },
    "leadership": {"leaders": [
        {"full_name": "Rodrigo Caserta", "title": "Chief Executive Officer", "previous_role": "ex-VP Client Services, Avanade LATAM", "accenture_alumni": False},
        {"full_name": "Adam Warby", "title": "Executive Chairman", "previous_role": "ex-CEO, Avanade", "accenture_alumni": True},
    ]},
    "glassdoor_news": {
        "glassdoor_rating": "3.8", "glassdoor_total_reviews": "4,312",
        "recent_news": [
            {"month_year": "February 2025", "description": "Avanade announced expansion of AI practice with 10,000 additional AI-certified professionals target by end of 2025"},
            {"month_year": "November 2024", "description": "Completed acquisition of Fellowmind, adding approximately 1,800 staff across Nordics and DACH"},
            {"month_year": "September 2024", "description": "Launched dedicated Microsoft Fabric practice to address enterprise data platform demand"},
        ],
    },
    "workforce": {
        "functions": [{"function_name": "Information Technology", "percentage": "62%"}, {"function_name": "Consulting", "percentage": "18%"}, {"function_name": "Engineering", "percentage": "9%"}, {"function_name": "Operations", "percentage": "6%"}, {"function_name": "Sales", "percentage": "5%"}],
        "locations": [{"location": "United States", "percentage": "24%"}, {"location": "India", "percentage": "22%"}, {"location": "United Kingdom", "percentage": "9%"}, {"location": "Australia", "percentage": "7%"}, {"location": "Germany", "percentage": "6%"}],
        "top_skills": ["Microsoft Azure", "Microsoft Dynamics 365", "Microsoft 365", "DevOps", "Agile", "Power BI", "C#", "Python", "Cybersecurity"],
        "open_positions": "1,847",
    },
    "strategic": {
        "strategic_strengths": ["Exclusive deep access to Microsoft product teams", "Multi-region delivery at scale", "Accenture and Microsoft dual-channel sales"],
        "key_risks": ["Concentrated dependency on Microsoft platform", "Parent JV ownership limits exit options", "High attrition in offshore delivery centers"],
        "strategic_fit_for_accenture": "Avanade already operates under 60% Accenture ownership. Microsoft platform depth — Dynamics 365, Azure, Security — complements Accenture's multi-cloud practice. Nordic and DACH coverage via Fellowmind fills a geographic gap for Accenture's SAP-adjacent Dynamics pipeline. Public Sector client base in North America and Europe aligns with Accenture Federal Services.",
        "ma_suitability": "Full acquisition requires Microsoft consent given its 40% stake. Valuation likely reflects 1.5–2.5x revenue multiple for a services-only firm. The commercially rational path is a structured buyout of Microsoft's 40% to consolidate Avanade onto Accenture's books. Deal complexity is high given JV governance constraints.",
    },
}

SIMULATE_DISCOVERY = {
    "acquirer": "Accenture",
    "thesis": {"sector": "Microsoft Dynamics consulting", "geography": "DACH + Nordics", "capability_gap": "SAP to Dynamics migration", "revenue_range": "$50M–$300M"},
    "targets": [
        {
            "company": "Fellowmind",
            "overview": {"business_overview": "Fellowmind is a Microsoft partner focused on business transformation using Microsoft technology stack in the Nordics and DACH region.", "legal_name": "Fellowmind", "company_type": "Private (PE-backed)", "year_founded": "2019", "hq": "Copenhagen, Denmark", "global_offices": "EMEA: Denmark (1), Sweden (1), Germany (2), Netherlands (1), Poland (1)", "employee_count": "1,800 (LinkedIn, Q1 2025)", "sector_industry": "IT Services — Microsoft Dynamics consulting", "business_model": "Fixed-price and time-and-materials Microsoft Dynamics 365 and Azure implementations", "certifications_awards": ["Microsoft Solutions Partner"], "website_url": "https://www.fellowmind.com", "linkedin_url": "https://www.linkedin.com/company/fellowmind"},
            "services": {"services_solutions_products": [{"name": "Microsoft Dynamics 365", "description": "ERP and CRM implementation across finance, supply chain, and sales modules"}, {"name": "Azure Cloud", "description": "Migration and managed services on Microsoft Azure"}, {"name": "Power Platform", "description": "Power Apps, Power BI, and Power Automate delivery"}]},
            "locations": {"headquarters": "Copenhagen, Denmark", "amer_offices": [], "emea_offices": ["Stockholm, Sweden", "Munich, Germany", "Frankfurt, Germany", "Amsterdam, Netherlands", "Warsaw, Poland"], "apac_offices": [], "delivery_centers": ["Warsaw, Poland (nearshore)"], "parent_company": "EQT-backed (PE ownership)"},
            "clients": {"named_clients": ["Vestas", "Ørsted", "Hempel"], "client_segments": ["Manufacturing", "Energy", "Financial Services"], "anonymous_case_studies": "Referenced"},
            "financials": {"revenue": "EUR 180M (FY2023, PitchBook)", "revenue_source": "PitchBook", "revenue_per_employee": "USD 100K", "funding_rounds": [{"date": "2021-03", "round_type": "PE Buyout", "amount": "Not disclosed", "lead_investors": "EQT"}], "acquisitions": [], "key_partnerships": ["Microsoft", "Orion", "Continia"]},
            "leadership": {"leaders": [{"full_name": "Søren Dalsgaard", "title": "Chief Executive Officer", "previous_role": "ex-CEO, Sunrise Technologies", "accenture_alumni": False}]},
            "glassdoor_news": {"glassdoor_rating": "4.1", "glassdoor_total_reviews": "312", "recent_news": [{"month_year": "November 2024", "description": "Acquired by Avanade as part of expansion into DACH and Nordic Microsoft Dynamics market"}, {"month_year": "June 2023", "description": "Expanded into Poland with nearshore delivery center acquisition"}]},
            "workforce": {"functions": [{"function_name": "Information Technology", "percentage": "70%"}, {"function_name": "Consulting", "percentage": "20%"}, {"function_name": "Operations", "percentage": "10%"}], "locations": [{"location": "Denmark", "percentage": "30%"}, {"location": "Germany", "percentage": "25%"}, {"location": "Poland", "percentage": "20%"}, {"location": "Netherlands", "percentage": "15%"}], "top_skills": ["Microsoft Dynamics 365", "Power Platform", "Azure", "F&O", "D365 CE"], "open_positions": "47"},
            "strategic": {"strategic_strengths": ["Deep Dynamics 365 F&O specialization", "Strong Nordic manufacturing client base", "Nearshore Poland delivery center"], "key_risks": ["PE ownership may inflate acquisition price", "Single-platform concentration risk", "Key-person dependency in Dynamics practice"], "strategic_fit_for_accenture": "Fellowmind provides Accenture with established Nordic and DACH Dynamics 365 delivery capacity. Its manufacturing and energy client base is underserved by Accenture's current SAP-heavy ERP practice in those markets. The Poland nearshore center complements Accenture's existing Eastern European delivery footprint.", "ma_suitability": "PE-backed at EQT, making it an available asset. Revenue of EUR 180M at an estimated 1.8x–2.5x revenue multiple implies a deal range of EUR 324M–450M. Integration complexity is medium given operational independence and geographic focus. Primary value is speed-to-market in DACH Dynamics 365 versus organic build."},
            "synergy": {"total_low_usd_m": 28, "total_high_usd_m": 52, "synergy_items": [{"synergy_type": "Revenue — cross-sell", "basis": "Accenture Dynamics practice upsell into Fellowmind's 3 named enterprise clients", "estimated_value_low_usd_m": 8, "estimated_value_high_usd_m": 18, "confidence_level": "Medium", "year_realizable": 2}, {"synergy_type": "Revenue — capability fill", "basis": "Accenture SAP clients migrating to Dynamics 365 in DACH; Fellowmind fills gap", "estimated_value_low_usd_m": 15, "estimated_value_high_usd_m": 28, "confidence_level": "Medium", "year_realizable": 2}, {"synergy_type": "Cost — headcount consolidation", "basis": "~15% G&A overlap on 1,800 headcount at est. USD 80K fully loaded", "estimated_value_low_usd_m": 5, "estimated_value_high_usd_m": 6, "confidence_level": "High", "year_realizable": 1}], "client_overlap": [], "geography_overlap": ["Germany"], "capability_gaps_filled": ["Microsoft Dynamics 365 F&O in DACH", "Nordic manufacturing sector coverage", "Nearshore Poland delivery"], "key_assumptions": ["Accenture retains full Fellowmind management team post-close", "No client attrition in year 1", "EQT seller willing to exit at 2.0–2.5x revenue", "Poland center maintained at current scale", "D365 F&O demand in DACH grows 15% YoY"], "deal_structure": "Full acquisition", "suggested_ev_revenue_multiple": "1.8x–2.5x (comparable: Coreview 2.1x, Sunrise Technologies 2.3x)", "integration_complexity": "Medium — geographically distinct from Accenture core, requires partner ecosystem alignment", "headline_rationale": "Fellowmind gives Accenture an immediate, established Dynamics 365 presence in the DACH and Nordic markets at lower risk than organic build."},
        }
    ],
}


# ── Persistence ───────────────────────────────────────────────────────────────
def _save(task_id: str):
    os.makedirs("projects", exist_ok=True)
    path = os.path.join("projects", f"{task_id}.json")
    try:
        with open(path, "w") as f:
            json.dump(tasks[task_id], f, indent=2)
    except Exception as e:
        print(f"[orch] Save failed for {task_id}: {e}")


def _log(task_id: str, msg: str, progress: int, agent: str = ""):
    tasks[task_id]["logs"].append(msg)
    tasks[task_id]["progress"] = progress
    if agent:
        tasks[task_id]["current_agent"] = agent
    safe_msg = msg.encode("ascii", errors="replace").decode("ascii")
    print(f"[{task_id[:8]}] {progress}% {safe_msg}")


# ── Intelligence profile pipeline ─────────────────────────────────────────────
def _profile_company(task_id: str, company: str, model: str, scraped: Dict, base_progress: int = 0, progress_range: int = 90) -> Dict:
    """Run full 9-agent intelligence profile. Returns results dict."""

    step = progress_range // 10

    _log(task_id, f"Agent 1: Company Profile — running", base_progress + step, "Agent 1 · Company Profile")
    overview = agent_company_overview(model, company, scraped)
    _log(task_id, "Agent 1: Company Profile — complete", base_progress + step * 2, "Agent 1 · Company Profile")

    _log(task_id, "Agent 2: Services & Products — running", base_progress + step * 2, "Agent 2 · Services & Products")
    services = agent_services(model, company, scraped)
    _log(task_id, "Agent 2: Services & Products — complete", base_progress + step * 3, "Agent 2 · Services & Products")

    _log(task_id, "Agents 3–8: Parallel research — running", base_progress + step * 3, "Agents 3–8 · Parallel Research")

    def run_loc():  return agent_locations(model, company, scraped)
    def run_cli():  return agent_clients(model, company, scraped)
    def run_fin():  return agent_financials(model, company, scraped)
    def run_lead(): return agent_leadership(model, company, scraped)
    def run_gd():   return agent_glassdoor_news(model, company, scraped)
    def run_wf():   return agent_workforce(model, company, scraped)

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(run_loc):  "locations",
            pool.submit(run_cli):  "clients",
            pool.submit(run_fin):  "financials",
            pool.submit(run_lead): "leadership",
            pool.submit(run_gd):   "glassdoor_news",
            pool.submit(run_wf):   "workforce",
        }
        res = {}
        for future in as_completed(futures):
            key = futures[future]
            res[key] = future.result()
            _log(task_id, f"Agent · {key} — complete", min(base_progress + step * 7, tasks[task_id]["progress"] + step), f"Agent · {key}")

    locations    = res.get("locations", {})
    clients      = res.get("clients", {})
    financials   = res.get("financials", {})
    leadership   = res.get("leadership", {})
    glassdoor    = res.get("glassdoor_news", {})
    workforce    = res.get("workforce", {})

    _log(task_id, "Agent 9: Strategic Intelligence — running", base_progress + step * 8, "Agent 9 · Strategic Intelligence")
    strategic = agent_strategic(model, company, overview, services, clients, financials, leadership, workforce, scraped)
    _log(task_id, "Agent 9: Strategic Intelligence — complete", base_progress + step * 9, "Agent 9 · Strategic Intelligence")

    return {
        "company":       company,
        "overview":      overview,
        "services":      services,
        "locations":     locations,
        "clients":       clients,
        "financials":    financials,
        "leadership":    leadership,
        "glassdoor_news": glassdoor,
        "workforce":     workforce,
        "strategic":     strategic,
    }


def _get_keys():
    try:
        import config as _cfg
        return (
            _cfg.OPENAI_API_KEY,
            _cfg.GOOGLE_API_KEY,
            getattr(_cfg, "XAI_API_KEY", ""),
            getattr(_cfg, "NVIDIA_API_KEY", ""),
        )
    except ImportError:
        return "", "", "", ""


def run_intelligence_pipeline(task_id: str, company: str, model: Optional[str], simulate: bool,
                               openai_key: str = "", gemini_key: str = "", grok_key: str = "", nvidia_key: str = ""):
    keys = _get_keys()
    openai_key = openai_key or keys[0]
    gemini_key = gemini_key or keys[1]
    grok_key   = grok_key   or keys[2]
    nvidia_key = nvidia_key or keys[3]
    tasks[task_id]["status"] = "running"
    m = model or OLLAMA_MODEL

    try:
        if simulate:
            import time
            _log(task_id, "Simulation mode: loading pre-built profile", 5, "Initializing")
            for step, msg in [
                (18, "Agent 1: Company Profile — complete"),
                (28, "Agent 2: Services & Products — complete"),
                (50, "Agents 3–6: Parallel research — complete"),
                (65, "Agent 7: Glassdoor & News — complete"),
                (78, "Agent 8: Workforce — complete"),
                (92, "Agent 9: Strategic Intelligence — complete"),
            ]:
                time.sleep(0.5)
                _log(task_id, msg, step, msg.split(" — ")[0])
            tasks[task_id]["results"] = {**SIMULATE_PROFILE}
            tasks[task_id].update({"status": "completed", "progress": 100, "current_agent": "Complete"})
            _save(task_id)
            return

        # ── Phase 0: Scrape real data ─────────────────────────────────────────
        llm_sources = [s for s, k in [("OpenAI", openai_key), ("Grok", grok_key), ("DeepSeek", nvidia_key), ("Gemini", gemini_key)] if k]
        src_note = f" + {'/'.join(llm_sources)}" if llm_sources else ""
        _log(task_id, f"Phase 0: Gathering data for {company}{src_note}...", 5, "Data Acquisition")
        scraped = gather_company_intelligence(company, openai_key=openai_key, gemini_key=gemini_key, grok_key=grok_key, nvidia_key=nvidia_key)
        page_count = len(scraped.get("website", {}))
        llm_used   = scraped.get("llm_research", {}).get("sources_used", [])
        fin_flag   = "public financials" if scraped.get("financials") else "private"
        _log(task_id, f"Data acquired: {page_count} pages, {fin_flag}, LLM={llm_used or 'none'}", 12, "Data Acquisition")

        # ── Phase 1–9: Intelligence agents ───────────────────────────────────
        results = _profile_company(task_id, company, m, scraped, base_progress=12, progress_range=83)

        # Attach scraped metadata for UI source chips
        results["_scraped_meta"] = {
            "website_pages":  len(scraped.get("website", {})),
            "wiki_ok":        bool(scraped.get("wiki", {}).get("extract")),
            "wikidata_ok":    bool(scraped.get("wikidata")),
            "sec_ok":         bool(scraped.get("sec")),
            "search_count":   sum(len(v) for v in scraped.get("search", {}).values()),
            "fin_ok":         bool(scraped.get("financials")),
            "deal_intel_ok":  bool(scraped.get("deal_intel", {}).get("context_str")),
        }
        results["_llm_sources"] = scraped.get("llm_research", {}).get("sources_used", [])
        tasks[task_id]["results"] = results
        tasks[task_id].update({"status": "completed", "progress": 100, "current_agent": "Complete"})
        _save(task_id)

    except Exception as e:
        tasks[task_id].update({"status": "failed", "error": str(e), "current_agent": "Error"})
        _log(task_id, f"CRITICAL ERROR: {e}", tasks[task_id].get("progress", 0), "Error")
        _save(task_id)


# ── Discovery pipeline ────────────────────────────────────────────────────────
def run_discovery_pipeline(task_id: str, acquirer: str, thesis: Dict, model: Optional[str], simulate: bool,
                            openai_key: str = "", gemini_key: str = "", grok_key: str = "", nvidia_key: str = ""):
    keys = _get_keys()
    openai_key = openai_key or keys[0]
    gemini_key = gemini_key or keys[1]
    grok_key   = grok_key   or keys[2]
    nvidia_key = nvidia_key or keys[3]
    tasks[task_id]["status"] = "running"
    m = model or OLLAMA_MODEL

    try:
        if simulate:
            import time
            _log(task_id, "Simulation: loading pre-built discovery results", 5, "Initializing")
            time.sleep(0.5)
            _log(task_id, f"Acquirer profiled: {SIMULATE_DISCOVERY['acquirer']}", 15, "Acquirer Profile")
            time.sleep(0.5)
            _log(task_id, "Target discovery: 1 candidate found", 25, "Target Discovery")
            time.sleep(0.5)
            _log(task_id, "Target 1: Fellowmind — intelligence gathering complete", 65, "Target 1 · Fellowmind")
            time.sleep(0.5)
            _log(task_id, "Target 1: Synergy model complete", 85, "Synergy Model")
            time.sleep(0.3)
            tasks[task_id]["results"] = {**SIMULATE_DISCOVERY}
            tasks[task_id].update({"status": "completed", "progress": 100, "current_agent": "Complete"})
            _save(task_id)
            return

        # ── Step 0: Scrape and profile acquirer ───────────────────────────────
        _log(task_id, f"Step 0: Gathering acquirer data: {acquirer}", 5, "Acquirer · Data Acquisition")
        acq_scraped = gather_company_intelligence(acquirer, openai_key=openai_key, gemini_key=gemini_key, grok_key=grok_key, nvidia_key=nvidia_key)
        llm_used = acq_scraped.get("llm_research", {}).get("sources_used", [])
        _log(task_id, f"Acquirer data acquired: {len(acq_scraped.get('website',{}))} pages, LLM={llm_used or 'none'}", 12, "Acquirer · Profiling")
        acq_profile = agent_acquirer_profile(m, acquirer, acq_scraped)
        _log(task_id, "Acquirer profile complete", 18, "Acquirer · Profiling")

        # ── Auto-fill empty thesis from acquirer profile ──────────────────────
        thesis = dict(thesis)  # avoid mutating caller's dict
        if not any(thesis.get(k) for k in ("sector", "geography", "capability_gap")):
            thesis["sector"]         = acq_profile.get("sector") or "technology services"
            thesis["geography"]      = (", ".join(acq_profile.get("geographies", [])[:2])) or "Global"
            thesis["capability_gap"] = (", ".join(acq_profile.get("capability_gaps", [])[:2])) or "digital transformation"
            _log(task_id,
                 f"Thesis auto-filled from acquirer profile — sector={thesis['sector']}, geo={thesis['geography']}, cap={thesis['capability_gap']}",
                 19, "Target Discovery")

        # ── Step 1: Discover targets ──────────────────────────────────────────
        _log(task_id, "Step 1: Searching for acquisition targets...", 20, "Target Discovery")

        target_names: List[str] = []
        rationales: List[str] = []

        # A: LLM-based discovery (OpenAI / Grok / Gemini) — if any key available
        if openai_key or gemini_key or grok_key or nvidia_key:
            from llm_research import research_discovery_targets
            active = [n for n, k in [("OpenAI", openai_key), ("Grok", grok_key), ("DeepSeek", nvidia_key), ("Gemini", gemini_key)] if k]
            _log(task_id, f"Querying {' + '.join(active)} for target suggestions...", 21, "Target Discovery")
            llm_disc = research_discovery_targets(acquirer, thesis, openai_key=openai_key, gemini_key=gemini_key, grok_key=grok_key, nvidia_key=nvidia_key)
            llm_names = [n for n in llm_disc.get("target_names", []) if _is_valid_target(n)][:8]
            if llm_names:
                target_names = llm_names
                acq_scraped["llm_discovery"] = llm_disc
                _log(task_id, f"LLM discovery found {len(target_names)} targets: {target_names}", 24, "Target Discovery")

        # B: DDG fallback if LLM discovery got nothing
        if not target_names:
            raw_snippets = discover_acquisition_targets(thesis)
            _log(task_id, f"DDG found {len(raw_snippets)} snippets, extracting names...", 24, "Target Discovery")
            if raw_snippets:
                extracted    = agent_extract_targets(m, raw_snippets, thesis)
                target_names = [n for n in extracted.get("company_names", [])[:6] if _is_valid_target(n)]
                rationales   = extracted.get("rationale_per_target", [])

        _log(task_id, f"Identified {len(target_names)} target candidates: {target_names}", 28, "Target Discovery")

        if not target_names:
            tasks[task_id]["results"] = {
                "acquirer": acquirer, "thesis": thesis, "targets": [],
                "error": "No targets found. Add OpenAI/Gemini API keys for better discovery, or use Simulation Mode.",
            }
            tasks[task_id].update({"status": "completed", "progress": 100, "current_agent": "Complete"})
            _save(task_id)
            return

        # ── Step 2: Profile each target ───────────────────────────────────────
        profiled_targets = []
        base = 28
        step_each = (65 - base) // max(len(target_names), 1)

        for i, tname in enumerate(target_names):
            pct = base + i * step_each
            _log(task_id, f"Target {i+1}/{len(target_names)}: Gathering data for {tname}...", pct, f"Target {i+1} · {tname}")
            tgt_scraped = gather_company_intelligence(tname, openai_key=openai_key, gemini_key=gemini_key, grok_key=grok_key, nvidia_key=nvidia_key)
            _log(task_id, f"Target {i+1}: Running intelligence agents…", pct + step_each // 3, f"Target {i+1} · {tname}")
            profile = _profile_company(task_id, tname, m, tgt_scraped, base_progress=pct, progress_range=step_each)
            profile["search_rationale"] = rationales[i] if i < len(rationales) else ""

            # ── Step 3a: LLM-powered synergy model (DeepSeek / OpenAI) ─────────
            _log(task_id, f"Target {i+1}: LLM synergy research…", pct + step_each - 3, f"Synergy Research · {tname}")
            llm_synergy: Dict = {}
            if openai_key or gemini_key or grok_key or nvidia_key:
                try:
                    from llm_research import research_synergy_model
                    llm_synergy = research_synergy_model(
                        acquirer, tname,
                        acq_scraped.get("llm_research", {}),
                        tgt_scraped.get("llm_research", {}),
                        tgt_scraped.get("deal_intel", {}),
                        openai_key=openai_key, gemini_key=gemini_key,
                        grok_key=grok_key, nvidia_key=nvidia_key,
                    ) or {}
                except Exception as _se:
                    print(f"[orchestrator] LLM synergy model failed for {tname}: {_se}")

            # ── Step 3b: Ollama synergy agent (local validation + fill) ──────
            _log(task_id, f"Target {i+1}: Computing synergy model…", pct + step_each - 2, f"Synergy · {tname}")
            synergy = agent_synergy_model(
                m, acquirer, tname,
                acq_profile,
                profile["overview"],
                profile["services"],
                profile["clients"],
                profile["financials"],
                profile["locations"],
                tgt_scraped.get("financials", {}),
                target_llm_research=tgt_scraped.get("llm_research", {}),
                target_deal_intel=tgt_scraped.get("deal_intel", {}),
                acquirer_llm_research=acq_scraped.get("llm_research", {}),
                llm_synergy=llm_synergy,
            )
            profile["synergy"] = synergy
            profiled_targets.append(profile)

        # ── Sort by synergy potential ─────────────────────────────────────────
        profiled_targets.sort(
            key=lambda t: t.get("synergy", {}).get("total_high_usd_m", 0),
            reverse=True,
        )

        tasks[task_id]["results"] = {
            "acquirer":  acquirer,
            "thesis":    thesis,
            "targets":   profiled_targets,
        }
        tasks[task_id].update({"status": "completed", "progress": 100, "current_agent": "Complete"})
        _save(task_id)

    except Exception as e:
        tasks[task_id].update({"status": "failed", "error": str(e), "current_agent": "Error"})
        _log(task_id, f"CRITICAL ERROR: {e}", tasks[task_id].get("progress", 0), "Error")
        _save(task_id)


# ── Public API ────────────────────────────────────────────────────────────────
def start_analysis_task(company: str, model: Optional[str] = None, simulate: bool = False) -> str:
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "task_id": task_id, "mode": "profile", "company": company,
        "status": "pending", "current_agent": "Initializing", "progress": 0,
        "logs": [], "results": None,
        "created_at": datetime.utcnow().isoformat(),
        "model": model or OLLAMA_MODEL, "simulate": simulate,
    }
    threading.Thread(
        target=run_intelligence_pipeline,
        args=(task_id, company, model, simulate),
        daemon=True,
    ).start()
    return task_id


def start_discovery_task(acquirer: str, thesis: Dict, model: Optional[str] = None, simulate: bool = False) -> str:
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "task_id": task_id, "mode": "discovery", "company": acquirer,
        "acquirer": acquirer, "thesis": thesis,
        "status": "pending", "current_agent": "Initializing", "progress": 0,
        "logs": [], "results": None,
        "created_at": datetime.utcnow().isoformat(),
        "model": model or OLLAMA_MODEL, "simulate": simulate,
    }
    threading.Thread(
        target=run_discovery_pipeline,
        args=(task_id, acquirer, thesis, model, simulate),
        daemon=True,
    ).start()
    return task_id
