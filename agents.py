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


def call_llm(prompt: str, schema_class, temperature: float = 0.1, model: Optional[str] = None) -> Dict[str, Any]:
    raw_schema = schema_class.model_json_schema()
    defs = raw_schema.get("$defs", {})
    flat = _inline_schema(raw_schema, defs)
    flat.pop("title", None)

    payload = {
        "model":   model or OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "format":   flat,
        "stream":   False,
        "options":  {"temperature": temperature, "num_ctx": 4096},
    }

    try:
        resp = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=180)
        resp.raise_for_status()
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


def _build_context(scraped: Dict[str, Any], search_keys: Optional[List[str]] = None) -> str:
    url = scraped.get("url", "")
    prefix = f"OFFICIAL WEBSITE URL: {url}\n\n" if url else ""
    return prefix + build_full_context(scraped, search_keys=search_keys)


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
) -> Dict:
    from scraper import format_financials_context
    # Build comparison context
    fin_ctx = format_financials_context(target_financials_raw)

    acq_clients  = acquirer_profile.get("named_clients", [])
    tgt_clients  = target_clients.get("named_clients", [])
    overlap      = list(set(c.lower() for c in acq_clients) & set(c.lower() for c in tgt_clients))

    acq_geos = acquirer_profile.get("geographies", [])
    tgt_geos = (target_locations.get("amer_offices", []) +
                target_locations.get("emea_offices", []) +
                target_locations.get("apac_offices", []))

    prompt = f"""{TONE}
You are a V&A Synergy Analyst quantifying M&A synergies.
Acquirer: {acquirer}
Target:   {target}

ACQUIRER PROFILE:
- Sector: {acquirer_profile.get('sector','')}
- Key services: {acquirer_profile.get('services',[])}
- Named clients: {acq_clients}
- Geographies: {acq_geos}
- Capability gaps: {acquirer_profile.get('capability_gaps',[])}
- Revenue: {acquirer_profile.get('revenue_estimate','')}
- Employees: {acquirer_profile.get('employee_count','')}

TARGET PROFILE:
- Sector: {target_overview.get('sector_industry','')}
- Services: {[s.get('name','') for s in target_services.get('services_solutions_products',[])[:6]]}
- Named clients: {tgt_clients}
- Revenue: {target_financials.get('revenue','')}
- Revenue/employee: {target_financials.get('revenue_per_employee','')}
- Employees: {target_overview.get('employee_count','')}
- Offices: {tgt_geos[:8]}
- Partnerships: {target_financials.get('key_partnerships',[])}

OVERLAP DETECTED:
- Common clients: {overlap if overlap else 'None identified in data'}
- Market data: {fin_ctx[:500]}

TASK — Produce a quantified synergy model.
Rules:
- Base ALL estimates on the data above. Do not invent figures.
- Where revenue data is available, size cross-sell as 2-5% of smaller entity's revenue per overlapping client segment.
- Where headcount is available, size G&A consolidation as 8-15% of combined headcount × average cost/employee.
- Use confidence=Low where data is insufficient, Medium where one data point exists, High where both entities' data supports the estimate.
- If a synergy cannot be estimated from the data, set both low and high to 0 and confidence=Low.
- suggested_ev_revenue_multiple must reference comparable sector transaction multiples if mentioned in search data.
"""
    return call_llm(prompt, SynergyModelOutput, 0.15, model)
