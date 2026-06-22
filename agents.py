import json
import requests
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

# ─── Structured Output Schemas ──────────────────────────────────────────────

class CapabilityGaps(BaseModel):
    capability_gaps: List[str] = Field(description="Internal skills or capabilities the acquirer lacks")
    market_gaps: List[str] = Field(description="Market segments or customer groups the acquirer cannot reach")
    technology_gaps: List[str] = Field(description="Technology or software gaps")
    customer_gaps: List[str] = Field(description="Gaps in the customer demographics or reach")
    geographic_gaps: List[str] = Field(description="Geographic areas where the acquirer lacks presence")

class StrategyOutput(BaseModel):
    business_model_summary: str = Field(description="Summary of the acquirer's current business model")
    strategic_priorities: List[str] = Field(description="Top 3-5 strategic priorities for the acquirer")
    acquisition_rationale: str = Field(description="Core thesis of why the company should acquire")
    gaps: CapabilityGaps = Field(description="Identified gaps that acquisitions can fill")

class IndustryOutput(BaseModel):
    structure: str = Field(description="Brief overview of the industry structure (fragmented, consolidated, etc.)")
    growth_trends: List[str] = Field(description="High-growth trends in the industry")
    consolidation_trends: List[str] = Field(description="Consolidation activities and trends")
    emerging_technologies: List[str] = Field(description="Disruptive or emerging technologies in the space")
    regulatory_trends: List[str] = Field(description="Key regulatory shifts or risks")
    attractive_categories: List[str] = Field(description="Acquisition categories/sub-industries that are attractive")
    disruption_risks: List[str] = Field(description="Disruption risks that could impact the industry")

class CandidateProfile(BaseModel):
    name: str = Field(description="Company Name")
    industry: str = Field(description="Primary industry focus")
    headquarters: str = Field(description="Headquarters city and country")
    revenue_estimate: str = Field(description="Estimated annual revenue (e.g. $50M - $100M)")
    employee_estimate: int = Field(description="Estimated number of employees")
    key_products: List[str] = Field(description="Key products or services offered")
    core_capabilities: List[str] = Field(description="Core strategic capabilities of the target")
    market_position: str = Field(description="Market position (e.g., niche player, regional leader)")
    strategic_fit_score: int = Field(description="Initial Strategic Fit score from 1-10")

class DiscoveryOutput(BaseModel):
    candidates: List[CandidateProfile] = Field(description="List of at least 20 acquisition candidates")

class SynergyDimension(BaseModel):
    score: int = Field(description="Score from 1 to 10")
    explanation: str = Field(description="Detailed evidence-based justification for this score")
    opportunities: List[str] = Field(description="Specific cross-sell, up-sell, or enhancement opportunities")

class StrategicSynergyOutput(BaseModel):
    strategic_fit: int = Field(description="Strategic Fit score from 1 to 10")
    revenue_synergy: SynergyDimension = Field(description="Revenue synergies evaluation")
    product_synergy: SynergyDimension = Field(description="Product synergies evaluation")
    market_synergy: SynergyDimension = Field(description="Market synergies evaluation")
    customer_synergy: SynergyDimension = Field(description="Customer base overlap and expansion evaluation")
    geographic_synergy: SynergyDimension = Field(description="Geographic reach expansion evaluation")

class TechnologyOutput(BaseModel):
    technology_synergy_score: int = Field(description="Technology Synergy Score from 1 to 10")
    tech_stack_analysis: str = Field(description="Analysis of compatibility between tech stacks")
    ip_and_patents: List[str] = Field(description="Key intellectual property, patents, or data assets identified")
    talent_and_platform_compatibility: str = Field(description="Assessment of engineering talent and platform alignment")

class FinancialMetric(BaseModel):
    revenue: str = Field(description="Estimated revenue of target")
    ebitda: str = Field(description="Estimated EBITDA of target")
    valuation_estimate: str = Field(description="Estimated transaction value / valuation range")
    growth_profile: str = Field(description="Historical or projected growth rate")

class FinancialOutput(BaseModel):
    target_financials: FinancialMetric = Field(description="Financial profile of the target")
    affordability_score: int = Field(description="Affordability score from 1 to 10 (10 = highly affordable)")
    financial_health_score: int = Field(description="Financial health score from 1 to 10 (10 = very strong)")
    roi_potential_score: int = Field(description="ROI Potential score from 1 to 10 (10 = high ROI)")
    value_creation_score: int = Field(description="Value Creation score from 1 to 10 (10 = high value creation)")
    financial_feasibility: str = Field(description="Detailed financial evaluation summary")

class RiskDimension(BaseModel):
    level: str = Field(description="Risk level: Low, Medium, High")
    description: str = Field(description="Specific description of the risk in this category")

class RiskOutput(BaseModel):
    risk_score: int = Field(description="Overall Risk Score from 1 to 10 (1 = Very Low, 10 = Very High)")
    strategic_risks: RiskDimension = Field(description="Risks of poor fit, overlap, or cannibalization")
    financial_risks: RiskDimension = Field(description="Risks of overvaluation, high integration costs, or debt burden")
    operational_risks: RiskDimension = Field(description="Risks of supply chain or operational incompatibility")
    technology_risks: RiskDimension = Field(description="Risks of obsolete tech or platform incompatibility")
    cultural_risks: RiskDimension = Field(description="Risks of leadership mismatch and talent retention issues")

class DevilsAdvocateOutput(BaseModel):
    why_deal_should_not_happen: str = Field(description="Answer: Why should this deal NOT happen?")
    weak_assumptions: str = Field(description="Answer: What assumptions are weak?")
    value_destruction_scenarios: str = Field(description="Answer: What value destruction scenarios exist?")
    post_merger_risks: str = Field(description="Answer: What could go wrong post-merger?")
    competitor_benefits: str = Field(description="Answer: Why might competitors benefit instead?")
    bear_case: str = Field(description="Comprehensive Bear Case summary")
    bull_case: str = Field(description="Comprehensive Bull Case summary")
    cultural_compatibility_score: int = Field(description="Cultural Compatibility Score from 1-10 based on analysis")

class TierRecommendation(BaseModel):
    company_name: str = Field(description="Name of the company")
    tier: str = Field(description="Tier (Tier 1: Immediate Acquisition Candidate, Tier 2: Strong Strategic Fit, Tier 3: Opportunistic Target, Tier 4: Monitor Only, Tier 5: Avoid)")
    rationalization: str = Field(description="Specific reason for this tier classification")

class PartnerOutput(BaseModel):
    critique: str = Field(description="Adversarial critique of other agents' findings and scores")
    hidden_opportunities: List[str] = Field(description="Identified hidden opportunities and synergies")
    hidden_risks: List[str] = Field(description="Identified hidden risks and integration challenges")
    recommendations_table: List[TierRecommendation] = Field(description="Tiering categorizations for the top targets")
    final_questions: Dict[str, str] = Field(description="Answers to the 5 core investment banking recommendation questions: "
                                                       "1. Which company should be acquired first? "
                                                       "2. Which acquisition generates maximum shareholder value? "
                                                       "3. Which acquisition is most feasible? "
                                                       "4. Which acquisition has the best risk-adjusted return? "
                                                       "5. What is the ideal acquisition roadmap for the next 3-5 years?")
    ideal_roadmap_milestones: List[str] = Field(description="3-5 year roadmap timeline items")


# ─── Ollama LLM ──────────────────────────────────────────────────────────────

OLLAMA_MODEL = "llama3.2:latest"
OLLAMA_BASE_URL = "http://localhost:11434"


def _inline_schema(schema: dict, defs: dict) -> dict:
    """Recursively resolve $ref references to inline the schema (remove $defs)."""
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


def call_llm(prompt: str, schema_class, temperature: float = 0.2, model: Optional[str] = None) -> Dict[str, Any]:
    raw_schema = schema_class.model_json_schema()
    defs = raw_schema.get("$defs", {})
    flat_schema = _inline_schema(raw_schema, defs)
    # Remove unsupported keys that trip up Ollama
    flat_schema.pop("title", None)

    payload = {
        "model": model or OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "format": flat_schema,
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": 8192},
    }

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=600,
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Cannot connect to Ollama at {OLLAMA_BASE_URL}. "
            "Make sure Ollama is running: `ollama serve`"
        )
    except requests.exceptions.HTTPError as e:
        # Log the response body for easier debugging
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        raise RuntimeError(f"Ollama API error ({resp.status_code}): {body}") from e

    result = resp.json()
    raw = result.get("message", {}).get("content", "")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        import re
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        return json.loads(cleaned)


# ─── Agent Functions ─────────────────────────────────────────────────────────

def run_corporate_strategy(model: Optional[str], acquirer: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"""You are Agent 1: Corporate Strategy Analyst. Your objective is to determine why the acquiring company should pursue acquisitions.
Acquiring Company: {acquirer}
Context / Parameters: {json.dumps(inputs, indent=2)}

Analyze:
- Business model
- Growth strategy
- Industry position
- Competitive advantages and weaknesses
- Revenue mix and product portfolio
- Customer segments and geographic presence
- Current challenges and future growth opportunities

Be rigorous and factual. Identify precise strategic gaps: capability gaps, market gaps, technology gaps, customer gaps, and geographic gaps."""

    return call_llm(prompt, StrategyOutput, 0.2, model)


def run_industry_intelligence(model: Optional[str], acquirer: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"""You are Agent 2: Industry Intelligence Analyst. Your objective is to map the industry landscape for potential acquisitions.
Acquiring Company: {acquirer}
Context / Parameters: {json.dumps(inputs, indent=2)}

Analyze:
- Industry structure (degree of fragmentation, consolidation trends)
- Growth trends and emerging technologies
- Regulatory trends and competitive threats

Identify attractive acquisition categories, high-growth segments, and key disruption risks."""

    return call_llm(prompt, IndustryOutput, 0.2, model)


def run_target_discovery(model: Optional[str], acquirer: str, strategy: Dict[str, Any], industry: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"""You are Agent 3: Acquisition Target Discovery Agent. Your objective is to generate acquisition candidates.
Acquiring Company: {acquirer}
Strategy Context: {json.dumps(strategy, indent=2)}
Industry Context: {json.dumps(industry, indent=2)}
Optional Parameters: {json.dumps(inputs, indent=2)}

Search for companies that satisfy strategic, geographic, technology, product, customer, and financial feasibility criteria (budget: {inputs.get('acquisition_budget', 'Not Specified')}).

Generate a longlist of at least 20 real or highly realistic companies. For each candidate provide:
- Company Name, Industry, Headquarters, Revenue estimate, Employee estimate
- Key products, Core capabilities, Market position
- An initial Strategic Fit score (1-10)

Ensure you return exactly 20 or more candidates."""

    return call_llm(prompt, DiscoveryOutput, 0.3, model)


def run_strategic_synergies(model: Optional[str], acquirer: str, target: Dict[str, Any], strategy: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"""You are Agent 4: Strategic Synergy Analyst. Your objective is to evaluate strategic synergies.
Acquiring Company: {acquirer}
Target Company Profile: {json.dumps(target, indent=2)}
Acquirer Strategy Gaps: {json.dumps(strategy.get('gaps', {}), indent=2)}

Evaluate in detail (Score 1-10 each):
1. Strategic Fit: Overall strategic alignment
2. Revenue Synergies: Cross-selling, upselling, customer and geographic expansion
3. Product Synergies: Portfolio overlap, complementarity, technology enhancement
4. Market Synergies: Market share, competitive strengthening
5. Customer Synergies: Demographic fit, customer expansion
6. Geographic Synergies: Market entry, geographic gap filling

Never assume synergy exists. Look for evidence. Penalize overlapping products with weak differentiation."""

    return call_llm(prompt, StrategicSynergyOutput, 0.2, model)


def run_technology_evaluation(model: Optional[str], acquirer: str, target: Dict[str, Any], strategy: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"""You are Agent 5: Technology & Innovation Analyst. Your objective is to evaluate technology compatibility.
Acquiring Company: {acquirer}
Target Company Profile: {json.dumps(target, indent=2)}
Acquirer Tech Gaps: {strategy.get('gaps', {}).get('technology_gaps', [])}

Analyze:
- Technology stack compatibility, IP portfolio and patents
- AI capabilities, data assets, engineering talent, platform compatibility

Output a Technology Synergy Score (1-10) and detailed analysis."""

    return call_llm(prompt, TechnologyOutput, 0.2, model)


def run_financial_evaluation(model: Optional[str], acquirer: str, target: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"""You are Agent 6: Financial Analyst. Your objective is to evaluate acquisition feasibility.
Acquiring Company: {acquirer}
Target Company Profile: {json.dumps(target, indent=2)}
Acquisition Budget/Financial Inputs: {json.dumps(inputs, indent=2)}

Analyze:
- Target financial metrics (Revenue, EBITDA, Valuation Estimate, Growth Profile)
- Affordability (1-10): Can the acquirer afford this?
- Financial Health (1-10): Profitability vs. cash burn
- ROI Potential (1-10): Expected returns on capital
- Value Creation (1-10): Long-term shareholder value

Penalize targets with poor profitability or that exceed the acquisition budget. Explicitly estimate valuation range using typical industry multiples."""

    return call_llm(prompt, FinancialOutput, 0.2, model)


def run_risk_assessment(model: Optional[str], acquirer: str, target: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"""You are Agent 7: Risk Assessment Agent. Your objective is to identify acquisition risks.
Acquiring Company: {acquirer}
Target Company Profile: {json.dumps(target, indent=2)}

Identify and score (Low, Medium, High) the following risks:
1. Strategic Risks: Weak fit, market overlap, product cannibalization
2. Financial Risks: Overvaluation, integration costs, debt burden
3. Operational Risks: Process incompatibility, supply chain conflicts
4. Technology Risks: Platform incompatibility, obsolete technology
5. Cultural Risks: Leadership mismatch, talent retention issues

Provide an overall Risk Score from 1 to 10 (1 = Very Low Risk, 10 = Very High Risk)."""

    return call_llm(prompt, RiskOutput, 0.2, model)


def run_devils_advocate(model: Optional[str], acquirer: str, target: Dict[str, Any], strategy: Dict[str, Any], financial: Dict[str, Any], risk: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"""You are Agent 8: Devil's Advocate Agent. Your objective is to challenge the acquisition thesis.
Acquiring Company: {acquirer}
Target: {json.dumps(target, indent=2)}
Strategic Fit / Synergy Context: {json.dumps(strategy, indent=2)}
Financial Assessment: {json.dumps(financial, indent=2)}
Risk Assessment: {json.dumps(risk, indent=2)}

For this target answer:
1. Why should this deal NOT happen? (Challenge the core thesis)
2. What assumptions are weak? (Question growth projections, cost savings, synergies)
3. What value destruction scenarios exist?
4. What could go wrong post-merger? (Integration friction)
5. Why might competitors benefit instead?

Generate an aggressive Bear Case, a balanced Bull Case, and assign a Cultural Compatibility Score (1-10)."""

    return call_llm(prompt, DevilsAdvocateOutput, 0.3, model)


def run_ma_partner(model: Optional[str], acquirer: str, top_targets_evaluations: List[Dict[str, Any]], inputs: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"""You are Agent 9: M&A Partner Agent. You act as a senior investment banker.
Acquiring Company: {acquirer}
Inputs: {json.dumps(inputs, indent=2)}

Detailed Evaluations of top candidates:
{json.dumps(top_targets_evaluations, indent=2)}

Tasks:
1. Review and critique the outputs from all agents. Challenge their assumptions.
2. Identify hidden opportunities and hidden risks/missing synergies.
3. Classify all evaluated targets into Tier 1 (Immediate Acquisition Candidate) through Tier 5 (Avoid).
4. Answer the 5 core M&A questions:
   - Which company should be acquired first?
   - Which acquisition generates maximum shareholder value?
   - Which acquisition is most feasible?
   - Which acquisition has the best risk-adjusted return?
   - What is the ideal acquisition roadmap for the next 3-5 years?

Provide an authoritative, high-value investment banking advisory recommendation."""

    return call_llm(prompt, PartnerOutput, 0.2, model)
