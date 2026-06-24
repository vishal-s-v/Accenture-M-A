import json
import re
import requests
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from scraper import build_full_context

# ── Tone rules injected into every prompt ─────────────────────────────────────
TONE = """
MANDATORY TONE & SOURCE RULES:
- Plain, precise, analytical English only. Zero marketing language.
- Banned words (and equivalents): cutting-edge, best-in-class, innovative, transformative,
  robust, seamlessly, empowers, game-changing, holistic, end-to-end, world-class,
  next-generation, dynamic, leverage, synergy (except as a section header).
- Extract facts ONLY from the provided scraped data context below.
- If a fact is not present in the provided context, output exactly: "Not found in allowed sources"
- Never invent figures, names, dates, or locations not present in the provided data.
- Do not add explanatory caveats; populate fields or state not-found.
"""

# ── Ollama config ─────────────────────────────────────────────────────────────
OLLAMA_MODEL    = "llama3.2:latest"
OLLAMA_BASE_URL = "http://localhost:11434"

# Per-agent context budget in chars.  ~3000 chars ≈ 750 tokens; leaves ~3300
# tokens in the 4096-token window for the instruction, schema, and output.
CONTEXT_CHAR_LIMIT       = 3000
CONTEXT_CHAR_LIMIT_RETRY = 1600   # halved budget used on timeout retry


# ── Schema inliner ────────────────────────────────────────────────────────────
def _inline_schema(schema: dict, defs: dict) -> dict:
    if "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        return _inline_schema(defs.get(ref_name, {}), defs)
    result = {}
    for k, v in schema.items():
        if k == "$defs":
            continue
        elif isinstance(v, dict):
            result[k] = _inline_schema(v, defs)
        elif isinstance(v, list):
            result[k] = [_inline_schema(i, defs) if isinstance(i, dict) else i for i in v]
        else:
            result[k] = v
    return result


def _truncate_prompt(prompt: str, data_char_limit: int) -> str:
    """
    Find the GROUNDED DATA / VERIFIED DATA block and truncate it to
    data_char_limit chars, leaving agent instructions intact.
    """
    for marker in ("GROUNDED DATA", "VERIFIED DATA", "ACQUIRER PROFILE"):
        idx = prompt.find(marker)
        if idx != -1:
            header = prompt[:idx + len(marker)]
            body   = prompt[idx + len(marker):]
            return header + body[:data_char_limit] + "\n[...context truncated...]"
    # Fallback: hard-truncate the whole prompt
    return prompt[: data_char_limit + 800]


def call_llm(prompt: str, schema_class, temperature: float = 0.1, model: Optional[str] = None) -> Dict[str, Any]:
    raw_schema = schema_class.model_json_schema()
    defs = raw_schema.get("$defs", {})
    flat = _inline_schema(raw_schema, defs)
    flat.pop("title", None)

    attempts = [prompt, _truncate_prompt(prompt, CONTEXT_CHAR_LIMIT_RETRY)]
    last_exc: Exception = RuntimeError("Unknown error")

    for i, attempt_prompt in enumerate(attempts):
        payload = {
            "model":   model or OLLAMA_MODEL,
            "messages": [{"role": "user", "content": attempt_prompt}],
            "format":   flat,
            "stream":   False,
            "options":  {"temperature": temperature, "num_ctx": 4096},
        }
        try:
            resp = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=300)
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            last_exc = RuntimeError("Ollama read timeout (300 s)")
            if i == 0:
                print(f"[agents] Timeout on full context; retrying with ~{CONTEXT_CHAR_LIMIT_RETRY} char batch...")
            continue
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"Cannot connect to Ollama at {OLLAMA_BASE_URL}. Run: ollama serve")
        except requests.exceptions.HTTPError as e:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            raise RuntimeError(f"Ollama API error ({resp.status_code}): {body}") from e

        raw = resp.json().get("message", {}).get("content", "")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
            return json.loads(cleaned)

    raise last_exc


def _build_context(scraped: Dict[str, Any], search_keys: Optional[List[str]] = None) -> str:
    url = scraped.get("url", "")
    prefix = f"OFFICIAL WEBSITE URL: {url}\n\n" if url else ""
    ctx = build_full_context(scraped, search_keys=search_keys)
    # Hard cap: keeps total prompt well within the 4096-token window
    return (prefix + ctx)[:CONTEXT_CHAR_LIMIT]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class CompanyOverviewOutput(BaseModel):
    business_overview: str = Field(description="3-4 sentences on scale, core focus, and market positioning extracted from provided data.")
    legal_name: str
    company_type: str = Field(description="Public, Private, PE-backed, VC-backed, Subsidiary, Joint Venture")
    year_founded: str
    hq: str = Field(description="City, State/Region, Country")
    global_offices: str = Field(description="Format: AMER: USA (2) | EMEA: UK (1) | APAC: Singapore (1)")
    employee_count: str = Field(description="Integer with source note, e.g. '4,200 (LinkedIn, Q1 2025)'")
    sector_industry: str
    business_model: str = Field(description="One sentence on revenue/delivery model")
    certifications_awards: List[str]
    website_url: str
    linkedin_url: str


class ServiceItem(BaseModel):
    name: str  = Field(description="Verbatim from website")
    description: str = Field(description="Plain factual description")

class ServicesOutput(BaseModel):
    services_solutions_products: List[ServiceItem]


class LocationsOutput(BaseModel):
    headquarters: str
    amer_offices: List[str]
    emea_offices: List[str]
    apac_offices: List[str]
    delivery_centers: List[str]
    parent_company: str


class ClientsOutput(BaseModel):
    named_clients: List[str] = Field(description="Up to 10 named clients, names only")
    client_segments: List[str]
    anonymous_case_studies: str


class FundingRound(BaseModel):
    date: str
    round_type: str
    amount: str
    lead_investors: str

class AcquisitionItem(BaseModel):
    company_name: str
    descriptor: str = Field(description="4-5 word descriptor")
    year: str
    deal_value: str
    headcount_added: str
    strategic_rationale: str = Field(description="Max 15 words, only if stated in sources")

class FinancialsOutput(BaseModel):
    revenue: str = Field(description="Most recent annual revenue with currency, fiscal year, source")
    revenue_source: str
    revenue_per_employee: str = Field(description="USD [X]K")
    funding_rounds: List[FundingRound]
    acquisitions: List[AcquisitionItem]
    key_partnerships: List[str]


class LeaderItem(BaseModel):
    full_name: str
    title: str
    previous_role: str = Field(description="ex-[Role, Company]")
    accenture_alumni: bool

class LeadershipOutput(BaseModel):
    leaders: List[LeaderItem]


class NewsItem(BaseModel):
    month_year: str
    description: str

class GlassdoorNewsOutput(BaseModel):
    glassdoor_rating: str
    glassdoor_total_reviews: str
    recent_news: List[NewsItem]


class WorkforceFunction(BaseModel):
    function_name: str
    percentage: str

class WorkforceLocation(BaseModel):
    location: str
    percentage: str

class WorkforceOutput(BaseModel):
    functions: List[WorkforceFunction]
    locations: List[WorkforceLocation]
    top_skills: List[str]
    open_positions: str


class StrategicOutput(BaseModel):
    strategic_strengths: List[str] = Field(description="Exactly 3 items, max 6 words each")
    key_risks: List[str] = Field(description="Exactly 3 items, max 6 words each")
    strategic_fit_for_accenture: str = Field(description="3-5 sentences, specific capabilities/geographies/clients")
    ma_suitability: str = Field(description="3-5 sentences on acquisition/partnership/vendor fit")


# ── Synergy model ─────────────────────────────────────────────────────────────
class SynergyItem(BaseModel):
    synergy_type: str = Field(description="e.g. 'Revenue — cross-sell', 'Cost — headcount consolidation', 'Revenue — capability fill'")
    basis: str = Field(description="Factual basis for estimate, max 20 words, from provided data only")
    estimated_value_low_usd_m: float = Field(description="Lower bound USD millions. Use 0 if not calculable.")
    estimated_value_high_usd_m: float = Field(description="Upper bound USD millions. Use 0 if not calculable.")
    confidence_level: str = Field(description="High, Medium, or Low based on data availability")
    year_realizable: int = Field(description="1, 2, or 3 — earliest year synergy is realizable post-close")

class SynergyModelOutput(BaseModel):
    total_low_usd_m: float
    total_high_usd_m: float
    synergy_items: List[SynergyItem]
    client_overlap: List[str] = Field(description="Client names appearing in both acquirer and target data")
    geography_overlap: List[str] = Field(description="Markets where both companies operate")
    capability_gaps_filled: List[str] = Field(description="What the target adds to the acquirer")
    key_assumptions: List[str] = Field(description="Max 5 assumptions, max 15 words each")
    deal_structure: str = Field(description="Full acquisition | Strategic minority stake | Joint venture | Partnership agreement")
    suggested_ev_revenue_multiple: str = Field(description="e.g. '1.5x–2.5x' based on sector comps from data")
    integration_complexity: str = Field(description="Low | Medium | High with one-sentence basis")
    headline_rationale: str = Field(description="One plain English sentence on why this deal makes sense")


# ── Acquirer profile for discovery mode ──────────────────────────────────────
class AcquirerProfile(BaseModel):
    name: str
    sector: str
    services: List[str]
    named_clients: List[str]
    geographies: List[str]
    capability_gaps: List[str] = Field(description="Areas where acquirer is weak or absent")
    revenue_estimate: str
    employee_count: str


# ── Target name extractor (discovery mode) ───────────────────────────────────
class DiscoveredTargets(BaseModel):
    company_names: List[str] = Field(description="List of 3-6 real company names extracted from search snippets that are plausible acquisition targets")
    rationale_per_target: List[str] = Field(description="One sentence per target explaining why it appeared in search results")


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def agent_company_overview(model: Optional[str], company: str, scraped: Dict) -> Dict:
    ctx = _build_context(scraped, ["general", "linkedin"])
    prompt = f"""{TONE}
You are Agent 1: Company Profile Analyst.
Company: {company}

GROUNDED DATA (use this as your only source):
{ctx}

Extract SECTION 1 (Business Overview, 3-4 sentences) and SECTION 2 (Company Overview fields)
from the data above. Output "Not found in allowed sources" for any field not in the data."""
    return call_llm(prompt, CompanyOverviewOutput, 0.1, model)


def agent_services(model: Optional[str], company: str, scraped: Dict) -> Dict:
    ctx = _build_context(scraped, ["general"])
    prompt = f"""{TONE}
You are Agent 2: Services & Products Analyst.
Company: {company}

GROUNDED DATA:
{ctx}

Extract all service, solution, and product names verbatim from the website data above.
Use exact capitalization and wording from the source. Follow each with a factual description
based only on the provided text."""
    return call_llm(prompt, ServicesOutput, 0.1, model)


def agent_locations(model: Optional[str], company: str, scraped: Dict) -> Dict:
    ctx = _build_context(scraped, ["general"])
    prompt = f"""{TONE}
You are Agent 3: Locations & Footprint Analyst.
Company: {company}

GROUNDED DATA:
{ctx}

Extract all office locations, delivery centers, and parent company information
from the data above only."""
    return call_llm(prompt, LocationsOutput, 0.1, model)


def agent_clients(model: Optional[str], company: str, scraped: Dict) -> Dict:
    ctx = _build_context(scraped, ["clients", "general"])
    prompt = f"""{TONE}
You are Agent 4: Customer & Market Intelligence Analyst.
Company: {company}

GROUNDED DATA:
{ctx}

Extract named clients (up to 10), client segments, and case study references
from the provided data only. If no clients are named in the data, state so."""
    return call_llm(prompt, ClientsOutput, 0.1, model)


def agent_financials(model: Optional[str], company: str, scraped: Dict) -> Dict:
    ctx = _build_context(scraped, ["funding", "general"])
    prompt = f"""{TONE}
You are Agent 5: Financial & M&A Intelligence Analyst.
Company: {company}

GROUNDED DATA (includes yfinance public market data if available):
{ctx}

Extract revenue, funding rounds, acquisitions, and partnerships from the data above.
For public companies, use the yfinance figures provided. For private companies, use
search snippet estimates but note the source explicitly in the revenue field."""
    return call_llm(prompt, FinancialsOutput, 0.1, model)


def agent_leadership(model: Optional[str], company: str, scraped: Dict) -> Dict:
    ctx = _build_context(scraped, ["leadership"])
    prompt = f"""{TONE}
You are Agent 6: Leadership Intelligence Analyst.
Company: {company}

GROUNDED DATA:
{ctx}

Extract leadership team from the provided data. Flag Accenture alumni.
Only include names that appear in the provided data."""
    return call_llm(prompt, LeadershipOutput, 0.1, model)


def agent_glassdoor_news(model: Optional[str], company: str, scraped: Dict) -> Dict:
    ctx = _build_context(scraped, ["glassdoor", "news"])
    prompt = f"""{TONE}
You are Agent 7: External Intelligence Analyst.
Company: {company}

GROUNDED DATA:
{ctx}

Extract Glassdoor rating/review count and recent news items from the data above.
Only report news that appears in the provided search results with dates."""
    return call_llm(prompt, GlassdoorNewsOutput, 0.1, model)


def agent_workforce(model: Optional[str], company: str, scraped: Dict) -> Dict:
    ctx = _build_context(scraped, ["linkedin", "general"])
    prompt = f"""{TONE}
You are Agent 8: Workforce Intelligence Analyst.
Company: {company}

GROUNDED DATA:
{ctx}

Extract workforce breakdown, skills, and open positions from the provided data.
Use LinkedIn search result snippets for headcount data if available."""
    return call_llm(prompt, WorkforceOutput, 0.1, model)


def agent_strategic(
    model: Optional[str],
    company: str,
    overview: Dict,
    services: Dict,
    clients: Dict,
    financials: Dict,
    leadership: Dict,
    workforce: Dict,
    scraped: Dict,
) -> Dict:
    from scraper import format_financials_context
    fin = scraped.get("financials", {})
    fin_ctx = format_financials_context(fin)
    prompt = f"""{TONE}
You are Agent 9: Accenture V&A Strategic Intelligence Analyst.
Company: {company}

VERIFIED DATA SUMMARY:
- Business model: {overview.get('business_model', '')}
- Sector: {overview.get('sector_industry', '')}
- Revenue: {financials.get('revenue', '')} | Revenue/Employee: {financials.get('revenue_per_employee', '')}
- Employees: {overview.get('employee_count', '')}
- Key services: {[s.get('name','') for s in services.get('services_solutions_products', [])[:6]]}
- Named clients: {clients.get('named_clients', [])}
- Key partnerships: {financials.get('key_partnerships', [])}
- Geographies: AMER: {overview.get('global_offices', '')}
- Acquisitions (10yr): {[a.get('company_name','') for a in financials.get('acquisitions', [])]}

MARKET DATA:
{fin_ctx}

Based ONLY on the verified data above, produce Section 11 Strategic Intelligence.
Strategic Strengths: exactly 3, max 6 words each, no marketing language.
Key Risks: exactly 3, max 6 words each, factual.
Strategic Fit for Accenture: 3-5 sentences, specific.
M&A Suitability: 3-5 sentences on acquisition/partner/vendor fit with deal structure view."""
    return call_llm(prompt, StrategicOutput, 0.1, model)


def agent_acquirer_profile(model: Optional[str], acquirer: str, scraped: Dict) -> Dict:
    ctx = _build_context(scraped, ["general", "clients"])
    prompt = f"""{TONE}
You are a V&A analyst building an acquirer profile.
Acquirer: {acquirer}

GROUNDED DATA:
{ctx}

Extract the acquirer's sector, key services, named clients, operating geographies,
and identify capability gaps (areas where they are weak or absent based on the data).
Use "Not found in allowed sources" for any missing field."""
    return call_llm(prompt, AcquirerProfile, 0.1, model)


def agent_extract_targets(model: Optional[str], search_snippets: List[Dict], thesis: Dict) -> Dict:
    snippets_text = "\n".join(
        f"  [{i+1}] {s.get('title','')} — {s.get('body','')}"
        for i, s in enumerate(search_snippets[:20])
    )
    prompt = f"""{TONE}
You are a V&A analyst extracting acquisition target names from web search results.
Investment thesis: sector={thesis.get('sector','')}, geography={thesis.get('geography','')},
capability_gap={thesis.get('capability_gap','')}, revenue_range={thesis.get('revenue_range','')}

SEARCH SNIPPETS (from DuckDuckGo):
{snippets_text}

Extract 3-6 real, distinct company names that appear in these snippets as plausible
acquisition targets matching the thesis. Do not invent names not in the snippets.
Exclude the acquirer itself and publicly-listed companies with market cap > $10B."""
    return call_llm(prompt, DiscoveredTargets, 0.1, model)


def agent_synergy_model(
    model: Optional[str],
    acquirer: str,
    target: str,
    acquirer_profile: Dict,
    target_overview: Dict,
    target_services: Dict,
    target_clients: Dict,
    target_financials: Dict,
    target_locations: Dict,
    target_financials_raw: Dict,
    target_llm_research: Optional[Dict] = None,
    target_deal_intel: Optional[Dict] = None,
    acquirer_llm_research: Optional[Dict] = None,
    llm_synergy: Optional[Dict] = None,
) -> Dict:
    from scraper import format_financials_context
    fin_ctx = format_financials_context(target_financials_raw)

    acq_clients = acquirer_profile.get("named_clients", [])
    tgt_clients = target_clients.get("named_clients", [])
    overlap     = list(set(c.lower() for c in acq_clients) & set(c.lower() for c in tgt_clients))
    acq_geos    = acquirer_profile.get("geographies", [])
    tgt_geos    = (target_locations.get("amer_offices", []) +
                   target_locations.get("emea_offices", []) +
                   target_locations.get("apac_offices", []))

    # ── Pull structured fields from LLM research (DeepSeek / OpenAI) ─────────
    tgt_lc  = (target_llm_research  or {}).get("collated", {})
    acq_lc  = (acquirer_llm_research or {}).get("collated", {})
    di_lc   = (target_deal_intel    or {}).get("collated", {})

    # Revenue: prefer scraped extraction, fall back to LLM collated
    def _best(scraped_val: str, lc_key: str, lc: Dict) -> str:
        if scraped_val and "not found" not in scraped_val.lower():
            return scraped_val
        return str(lc.get(lc_key) or "") or "Not available"

    tgt_revenue     = _best(target_financials.get("revenue", ""),        "revenue",      tgt_lc)
    tgt_rev_emp     = _best(target_financials.get("revenue_per_employee",""), "revenue",  tgt_lc)
    tgt_employees   = _best(target_overview.get("employee_count", ""),   "employees",    tgt_lc)
    acq_revenue     = _best(acquirer_profile.get("revenue_estimate", ""),"revenue",      acq_lc)
    acq_employees   = _best(acquirer_profile.get("employee_count", ""),  "employees",    acq_lc)

    tgt_valuation   = tgt_lc.get("valuation_or_ev")   or ""
    tgt_ebitda      = tgt_lc.get("ebitda_margin")      or ""
    tgt_ownership   = tgt_lc.get("ownership")          or target_overview.get("company_type", "")
    tgt_competitors = tgt_lc.get("competitors")        or []
    tgt_growth      = tgt_lc.get("growth_signals")     or []
    tgt_pe          = tgt_lc.get("pe_details")         or {}
    tgt_certs       = tgt_lc.get("certifications")     or []
    tgt_verticals   = tgt_lc.get("key_client_verticals") or []

    # Build supplementary LLM context blocks
    llm_ctx_lines = []
    if (target_llm_research or {}).get("context_str"):
        llm_ctx_lines.append(f"TARGET LLM RESEARCH:\n{target_llm_research['context_str'][:700]}")
    if (target_deal_intel or {}).get("context_str"):
        llm_ctx_lines.append(f"TARGET DEAL INTELLIGENCE:\n{target_deal_intel['context_str'][:600]}")
    if (acquirer_llm_research or {}).get("context_str"):
        llm_ctx_lines.append(f"ACQUIRER LLM RESEARCH:\n{acquirer_llm_research['context_str'][:400]}")
    llm_supplement = "\n\n".join(llm_ctx_lines)

    prompt = f"""{TONE}
You are a V&A Synergy Analyst quantifying M&A synergies.
Acquirer: {acquirer}
Target:   {target}

ACQUIRER PROFILE (verified data):
- Sector: {acquirer_profile.get('sector','')}
- Key services: {acquirer_profile.get('services',[])}
- Named clients: {acq_clients}
- Geographies: {acq_geos}
- Capability gaps: {acquirer_profile.get('capability_gaps',[])}
- Revenue: {acq_revenue}
- Employees: {acq_employees}

TARGET PROFILE (verified data):
- Sector: {target_overview.get('sector_industry','')}
- Company type / Ownership: {tgt_ownership}
- Services: {[s.get('name','') for s in target_services.get('services_solutions_products',[])[:6]]}
- Named clients: {tgt_clients}
- Client verticals: {tgt_verticals}
- Revenue: {tgt_revenue}
- Revenue/Employee: {tgt_rev_emp}
- EBITDA Margin: {tgt_ebitda if tgt_ebitda else 'Not available'}
- EV / Valuation: {tgt_valuation if tgt_valuation else 'Not available'}
- Employees: {tgt_employees}
- Offices: {tgt_geos[:8]}
- Partnerships: {target_financials.get('key_partnerships',[])}
- Certifications: {tgt_certs}
- Competitors: {tgt_competitors}
- Growth signals: {tgt_growth}
- PE details: {tgt_pe if tgt_pe else 'N/A'}

OVERLAP DETECTED:
- Common clients: {overlap if overlap else 'None identified in data'}
- Public market data: {fin_ctx[:400]}

{llm_supplement}

TASK — Produce a rigorously quantified synergy model using ALL data above.

ESTIMATION RULES (apply in order):
1. If exact revenue is known, size revenue synergies as 3-5% of the smaller entity's annual revenue per overlapping client segment.
2. If revenue is unknown but employee count is available, estimate revenue as employees × $120,000 (IT services benchmark) or employees × $80,000 (other sectors) — note this as an estimate.
3. Size G&A cost synergies as 10-15% of estimated duplicate back-office headcount × $85,000 fully-loaded cost.
4. Size technology/platform synergies (shared tools, reduced vendor costs) at $2M–$8M for sub-500-person targets, $5M–$20M for 500-2000 person targets.
5. ALWAYS produce at least 2 synergy_items — one revenue and one cost — even with sparse data; use confidence=Low and explicit assumption notes.
6. Use confidence=Low for benchmark estimates, Medium for single-source data, High when multiple sources agree.
7. For suggested_ev_revenue_multiple, reference the target's sector: IT services 1.5x–3x, SaaS 4x–8x, Healthcare 2x–5x, Consulting 1x–2.5x, Other 1x–2x.
8. deal_structure MUST be one of: "Full acquisition", "Strategic minority stake", "Joint venture", "Partnership agreement" — choose based on ownership type and strategic fit.
9. integration_complexity: Low = same sector, same geo, similar culture; High = cross-sector, multi-region, PE exit; Medium otherwise. Always add a one-sentence reason.
10. headline_rationale: ONE sentence combining acquirer's capability gap and target's key strength — never leave blank.
"""
    result = call_llm(prompt, SynergyModelOutput, 0.15, model)

    # ── Post-processing: prefer deal_intel values from DeepSeek when richer ──
    tgt_sector = target_overview.get("sector_industry", "") or target_overview.get("sector", "")
    caps = result.get("capability_gaps_filled") or []
    cap_str = ", ".join(caps[:2]) if caps else "complementary capabilities"

    # Prefer deal_intel EV multiple (computed by DeepSeek) over Ollama default
    if di_lc.get("estimated_ev_revenue_multiple"):
        if not result.get("suggested_ev_revenue_multiple") or result.get("suggested_ev_revenue_multiple") in ("", "N/M", "N/M — insufficient revenue data"):
            result["suggested_ev_revenue_multiple"] = di_lc["estimated_ev_revenue_multiple"]

    # Prefer deal_intel deal structure when more specific
    if di_lc.get("deal_structure_recommendation") and not result.get("deal_structure"):
        result["deal_structure"] = di_lc["deal_structure_recommendation"]

    # Prefer deal_intel integration complexity (richer basis)
    if di_lc.get("integration_complexity") and di_lc.get("integration_complexity_basis"):
        if not result.get("integration_complexity") or "requires additional" in (result.get("integration_complexity") or ""):
            result["integration_complexity"] = f"{di_lc['integration_complexity']} — {di_lc['integration_complexity_basis']}"

    # Absolute fallbacks so UI never shows N/A
    if not result.get("deal_structure"):
        result["deal_structure"] = "Full acquisition"
    if not result.get("integration_complexity"):
        result["integration_complexity"] = "Medium — cross-sector deal requires detailed integration planning"
    if not result.get("suggested_ev_revenue_multiple"):
        # Use sector-based default
        sector_low = tgt_sector.lower()
        if "saas" in sector_low or "software" in sector_low:
            result["suggested_ev_revenue_multiple"] = "4.0x–7.0x (SaaS sector benchmark)"
        elif "health" in sector_low or "pharma" in sector_low or "bio" in sector_low:
            result["suggested_ev_revenue_multiple"] = "2.5x–5.0x (Healthcare sector benchmark)"
        elif "consult" in sector_low or "services" in sector_low or "technology" in sector_low:
            result["suggested_ev_revenue_multiple"] = "1.5x–2.5x (IT services sector benchmark)"
        else:
            result["suggested_ev_revenue_multiple"] = "1.0x–2.5x (general services benchmark)"
    if not result.get("headline_rationale"):
        result["headline_rationale"] = (
            f"Acquisition of {target} ({tgt_sector}) by {acquirer} fills the gap in {cap_str}, "
            "with synergy sizing subject to financial diligence."
        )

    # ── Merge LLM synergy (DeepSeek) when Ollama produced zeros ─────────────
    llm_syn_data = (llm_synergy or {}).get("collated", {})
    if llm_syn_data:
        # Override synergy items entirely when Ollama returned empty/zero
        ollama_low = result.get("total_low_usd_m", 0) or 0
        llm_low    = llm_syn_data.get("total_low_usd_m", 0) or 0
        if (ollama_low == 0 or not result.get("synergy_items")) and llm_low > 0:
            result["synergy_items"]   = llm_syn_data.get("synergy_items", [])
            result["total_low_usd_m"] = llm_low
            result["total_high_usd_m"]= llm_syn_data.get("total_high_usd_m", 0) or 0
            result["key_assumptions"] = llm_syn_data.get("key_assumptions", [])

        # Fill missing string fields from LLM synergy
        for field in ("deal_structure", "integration_complexity", "suggested_ev_revenue_multiple",
                      "headline_rationale", "capability_gaps_filled", "client_overlap", "geography_overlap"):
            if not result.get(field) and llm_syn_data.get(field):
                result[field] = llm_syn_data[field]

    # If total synergy is still zero but synergy_items were produced, sum them
    items = result.get("synergy_items") or []
    if result.get("total_low_usd_m", 0) == 0 and items:
        result["total_low_usd_m"]  = round(sum(i.get("estimated_value_low_usd_m",  0) for i in items), 1)
        result["total_high_usd_m"] = round(sum(i.get("estimated_value_high_usd_m", 0) for i in items), 1)

    return result
