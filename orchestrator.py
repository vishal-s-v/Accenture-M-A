import os
import json
import time
import uuid
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional

from agents import OLLAMA_MODEL
from agents import (
    run_corporate_strategy,
    run_industry_intelligence,
    run_target_discovery,
    run_strategic_synergies,
    run_technology_evaluation,
    run_financial_evaluation,
    run_risk_assessment,
    run_devils_advocate,
    run_ma_partner,
)

tasks: Dict[str, Dict[str, Any]] = {}


def calculate_synergy_score(
    strategic_fit: float,
    revenue_synergy: float,
    product_synergy: float,
    technology_synergy: float,
    customer_synergy: float,
    geographic_synergy: float,
    financial_feasibility: float,
    risk_score: float,
    cultural_compatibility: float,
) -> float:
    raw = (
        (strategic_fit * 0.20)
        + (revenue_synergy * 0.15)
        + (product_synergy * 0.10)
        + (technology_synergy * 0.10)
        + (customer_synergy * 0.10)
        + (geographic_synergy * 0.10)
        + (financial_feasibility * 0.10)
        + ((10 - risk_score) * 0.10)
        + (cultural_compatibility * 0.05)
    )
    return round(max(0.0, min(10.0, raw)) * 10.0, 1)


def _evaluate_target(model: Optional[str], acquirer: str, target: Dict[str, Any], strategy: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Agent execution order per target:
      4. Technology  ┐
      5. Financial   ├─ parallel
      6. Risk        ┘
      7. Strategic Synergies  (sequential — after above)
      8. Devil's Advocate     (sequential — needs risk + financial)
    """
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_tech = pool.submit(run_technology_evaluation, model, acquirer, target, strategy)
        f_fin  = pool.submit(run_financial_evaluation,  model, acquirer, target, inputs)
        f_risk = pool.submit(run_risk_assessment,       model, acquirer, target)

        tech     = f_tech.result()
        financial = f_fin.result()
        risk     = f_risk.result()

    synergies      = run_strategic_synergies(model, acquirer, target, strategy)
    devils_advocate = run_devils_advocate(model, acquirer, target, strategy, financial, risk)

    weighted = calculate_synergy_score(
        strategic_fit=synergies.get("strategic_fit", 5),
        revenue_synergy=synergies.get("revenue_synergy", {}).get("score", 5),
        product_synergy=synergies.get("product_synergy", {}).get("score", 5),
        technology_synergy=tech.get("technology_synergy_score", 5),
        customer_synergy=synergies.get("customer_synergy", {}).get("score", 5),
        geographic_synergy=synergies.get("geographic_synergy", {}).get("score", 5),
        financial_feasibility=financial.get("affordability_score", 5),
        risk_score=risk.get("risk_score", 5),
        cultural_compatibility=devils_advocate.get("cultural_compatibility_score", 5),
    )

    return {
        "profile": target,
        "synergies": synergies,
        "technology": tech,
        "financial": financial,
        "risk": risk,
        "devils_advocate": devils_advocate,
        "weighted_synergy_score": weighted,
    }


def run_orchestration_pipeline(
    task_id: str,
    acquirer: str,
    inputs: Dict[str, Any],
    model: Optional[str] = None,
    simulate: bool = False,
):
    task = tasks[task_id]
    model = model or OLLAMA_MODEL

    try:
        if simulate:
            run_simulation(task_id, acquirer, inputs)
            return

        task["logs"].append(f"Initializing Ollama pipeline with model: {model}...")

        # Agent 1 ─ Corporate Strategy
        task["status"] = "running"
        task["current_agent"] = "Corporate Strategy Analyst"
        task["progress"] = 10
        task["logs"].append("Agent 1 [Corporate Strategy Analyst] starting analysis...")
        strategy_output = run_corporate_strategy(model, acquirer, inputs)
        task["results"]["strategy"] = strategy_output
        task["logs"].append("Agent 1 completed.")

        # Agent 2 ─ Industry Intelligence
        task["current_agent"] = "Industry Intelligence Analyst"
        task["progress"] = 20
        task["logs"].append("Agent 2 [Industry Intelligence Analyst] analyzing market trends...")
        industry_output = run_industry_intelligence(model, acquirer, inputs)
        task["results"]["industry"] = industry_output
        task["logs"].append("Agent 2 completed.")

        # Agent 3 ─ Target Discovery
        task["current_agent"] = "Acquisition Target Discovery Agent"
        task["progress"] = 35
        task["logs"].append("Agent 3 [Target Discovery] searching for candidates...")
        discovery_output = run_target_discovery(model, acquirer, strategy_output, industry_output, inputs)
        candidates = discovery_output.get("candidates", [])
        task["results"]["discovery"] = discovery_output
        task["logs"].append(f"Agent 3 discovered {len(candidates)} acquisition candidates.")

        if len(candidates) < 20:
            task["logs"].append(f"Warning: Only {len(candidates)} candidates found (target: 20). Proceeding.")

        sorted_candidates = sorted(candidates, key=lambda x: x.get("strategic_fit_score", 0), reverse=True)
        top_10 = sorted_candidates[:10]
        remaining = sorted_candidates[10:]
        task["logs"].append(f"Selected top {len(top_10)} candidates for deep M&A evaluation.")

        top_evaluations = []
        progress_per_target = 45.0 / max(1, len(top_10))

        for idx, target in enumerate(top_10):
            target_name = target.get("name", f"Target {idx+1}")
            task["current_agent"] = f"Deep Evaluation: {target_name}"
            task["logs"].append(f"[{idx+1}/{len(top_10)}] Evaluating {target_name} (agents 4–8 in parallel)...")

            try:
                eval_result = _evaluate_target(model, acquirer, target, strategy_output, inputs)
                top_evaluations.append(eval_result)
                task["progress"] = int(35 + (idx + 1) * progress_per_target)
                score = eval_result["weighted_synergy_score"]
                risk = eval_result["risk"]["risk_score"]
                task["logs"].append(f"  ✓ {target_name} — Synergy: {score}/100, Risk: {risk}/10")
            except Exception as e:
                task["logs"].append(f"  ✗ {target_name} failed evaluation: {str(e)[:120]}")

        # Agent 9 ─ M&A Partner
        task["current_agent"] = "M&A Partner Agent"
        task["progress"] = 90
        task["logs"].append("Agent 9 [M&A Partner] reviewing all findings...")
        partner_output = run_ma_partner(model, acquirer, top_evaluations, inputs)
        task["results"]["partner"] = partner_output
        task["logs"].append("Agent 9 report finalized.")

        # Build longlist
        top_evaluations_sorted = sorted(top_evaluations, key=lambda x: x["weighted_synergy_score"], reverse=True)
        longlist = []
        rank = 1
        for te in top_evaluations_sorted:
            longlist.append({
                "rank": rank,
                "company": te["profile"]["name"],
                "industry": te["profile"]["industry"],
                "strategic_fit": te["synergies"]["strategic_fit"],
                "synergy_score": te["weighted_synergy_score"],
                "risk_score": te["risk"]["risk_score"],
                "evaluated": True,
            })
            rank += 1
        for t_rem in remaining:
            longlist.append({
                "rank": rank,
                "company": t_rem["name"],
                "industry": t_rem["industry"],
                "strategic_fit": t_rem["strategic_fit_score"],
                "synergy_score": "N/A",
                "risk_score": "N/A",
                "evaluated": False,
            })
            rank += 1

        task["results"]["longlist"] = longlist
        task["results"]["top_evaluations"] = top_evaluations_sorted

        save_task_to_disk(task_id)

        task["progress"] = 100
        task["status"] = "completed"
        task["logs"].append("✓ M&A Discovery and Synergy Evaluation completed successfully!")

    except Exception as e:
        task["status"] = "failed"
        task["logs"].append(f"CRITICAL ERROR: {str(e)}")
        task["logs"].append(traceback.format_exc())
        print(f"Pipeline error: {e}")
        traceback.print_exc()


def save_task_to_disk(task_id: str):
    os.makedirs("projects", exist_ok=True)
    with open(f"projects/{task_id}.json", "w") as f:
        json.dump(tasks[task_id], f, indent=2)


def start_analysis_task(
    acquirer: str,
    inputs: Dict[str, Any],
    model: Optional[str] = None,
    simulate: bool = False,
) -> str:
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "task_id": task_id,
        "acquirer": acquirer,
        "inputs": inputs,
        "model": model or OLLAMA_MODEL,
        "simulate": simulate,
        "status": "queued",
        "current_agent": "None",
        "progress": 0,
        "logs": ["Analysis queued. Background pipeline starting..."],
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": {},
    }

    thread = threading.Thread(
        target=run_orchestration_pipeline,
        args=(task_id, acquirer, inputs, model, simulate),
        daemon=True,
    )
    thread.start()
    return task_id


def run_simulation(task_id: str, acquirer: str, inputs: Dict[str, Any]):
    task = tasks[task_id]
    task["status"] = "running"

    industry_focus = inputs.get("industry_focus", "Technology & Digital Services")
    budget = inputs.get("acquisition_budget", "$200M – $500M")

    steps = [
        ("Corporate Strategy Analyst", 10, f"Analyzing internal value chain and capabilities of {acquirer}..."),
        ("Industry Intelligence Analyst", 20, f"Mapping {industry_focus} competitive landscape..."),
        ("Acquisition Target Discovery Agent", 35, "Scanning market databases and compiling longlist of 20 targets..."),
    ]
    for agent, progress, log in steps:
        task["current_agent"] = agent
        task["progress"] = progress
        task["logs"].append(log)
        time.sleep(1.0)
        task["logs"].append(f"Agent '{agent}' completed analysis.")

    candidate_names = [
        "Synthetix AI", "CloudSentry", "AeroTech Solutions", "Quantalytix", "InnoWave Systems",
        "Apex Digital", "DataCore Systems", "Stratus Cloud", "BlueShift Labs", "Nova Analytics",
        "Pinnacle Cyber", "Integra Software", "Element Security", "Vanguard AI", "Logix Systems",
        "Vertigo Labs", "Hyperion Data", "Zenith Consulting", "CoreLogic IT", "Aegis Software",
    ]

    candidates = [
        {
            "name": name,
            "industry": industry_focus,
            "headquarters": "New York, USA" if i % 2 == 0 else "London, UK",
            "revenue_estimate": f"${10 + (20 - i) * 3}M – ${20 + (20 - i) * 4}M",
            "employee_estimate": 50 + (20 - i) * 10,
            "key_products": [f"{name} Platform v2", f"{name} Managed Engine"],
            "core_capabilities": ["Cloud Native Migration", "Predictive ML Modeling", "Enterprise Integration"],
            "market_position": "Niche Challenger" if i > 5 else "Regional Leader",
            "strategic_fit_score": max(1, 9 - (i // 3)),
        }
        for i, name in enumerate(candidate_names)
    ]

    task["results"]["strategy"] = {
        "business_model_summary": "Core consulting and systems integration business with strong enterprise relationships but facing pressure from AI-automated workflows.",
        "strategic_priorities": [
            "Accelerate AI integration across key verticals",
            "Expand high-margin consulting capabilities",
            "Establish leadership in cloud cybersecurity solutions",
        ],
        "acquisition_rationale": "To bridge the technology gap in GenAI engineering and cyber compliance before boutique firms erode market share.",
        "gaps": {
            "capability_gaps": ["Generative AI Fine-tuning", "Zero-Trust Cloud Architecture"],
            "market_gaps": ["Mid-Market Enterprise Segment"],
            "technology_gaps": ["Proprietary Automated DevSecOps Platforms"],
            "customer_gaps": ["Digital Native Tech Startups"],
            "geographic_gaps": ["Nordic Region", "DACH Region presence"],
        },
    }

    task["results"]["industry"] = {
        "structure": "Highly fragmented in consulting segments; rapid consolidation at the top with large integrators purchasing AI-native boutiques.",
        "growth_trends": ["Generative AI integration (CAGR +34%)", "Hybrid Cloud Security orchestration"],
        "consolidation_trends": ["PE rollups of mid-sized IT consultancies", "Hyperscaler partner network mergers"],
        "emerging_technologies": ["Retrieval-Augmented Generation", "Agentic Workflow Orchestrators", "Quantum Encryption Readiness"],
        "regulatory_trends": ["EU AI Act compliance enforcement", "Strict data sovereignty laws"],
        "attractive_categories": ["AI Boutique Agencies", "B2B SaaS Security Tools", "Managed Cloud Integrators"],
        "disruption_risks": ["AI-driven automated coding reducing consultant headcount requirements"],
    }

    top_evaluations = []
    for idx, name in enumerate(candidate_names[:10]):
        task["current_agent"] = f"Evaluating target: {name}"
        task["logs"].append(f"[{idx+1}/10] Running deep evaluation for {name} (agents 4–8 in parallel)...")
        time.sleep(0.4)

        strat_fit = max(1, 9 - (idx // 3))
        rev_syn = max(1, 8 - (idx % 3))
        prod_syn = max(1, 7 - (idx % 2))
        tech_syn = max(1, 8 - (idx // 4))
        cust_syn = max(1, 9 - (idx % 4))
        geo_syn = max(1, 7 - (idx // 5))
        fin_feas = 6 + (idx % 3)
        risk_score = 3 + (idx % 4)
        cult_comp = max(1, 8 - (idx // 3))

        weighted = calculate_synergy_score(strat_fit, rev_syn, prod_syn, tech_syn, cust_syn, geo_syn, fin_feas, risk_score, cult_comp)

        top_evaluations.append({
            "profile": {
                "name": name,
                "industry": industry_focus,
                "headquarters": "New York, USA" if idx % 2 == 0 else "London, UK",
                "revenue_estimate": f"${20 + (10 - idx) * 5}M",
                "employee_estimate": 60 + (10 - idx) * 15,
                "key_products": [f"{name} Platform v2", f"{name} Cloud Engine"],
                "core_capabilities": ["Generative AI fine-tuning", "Advanced analytics"],
                "market_position": "Niche Leader" if idx < 3 else "Rising Challenger",
                "strategic_fit_score": strat_fit,
            },
            "synergies": {
                "strategic_fit": strat_fit,
                "revenue_synergy": {
                    "score": rev_syn,
                    "explanation": f"High potential for cross-selling {name}'s AI expertise to {acquirer}'s existing enterprise client base.",
                    "opportunities": ["Bundle AI engineering with legacy cloud integration packages", "Upsell advanced security modules"],
                },
                "product_synergy": {
                    "score": prod_syn,
                    "explanation": "Complementary portfolios. Target's proprietary tools integrate directly into client delivery portals.",
                    "opportunities": ["Integrate target AI agent engine into core dashboard", "Consolidate consulting delivery tools"],
                },
                "market_synergy": {
                    "score": 8,
                    "explanation": "Acquisition dramatically strengthens market share in mid-market tech vertical.",
                    "opportunities": ["Ecosystem expansion with key hyperscalers", "Co-marketing new service offerings"],
                },
                "customer_synergy": {
                    "score": cust_syn,
                    "explanation": "Virtually zero client overlap. Target services mid-market tech; acquirer services Fortune 500.",
                    "opportunities": ["Cross-sell enterprise scale solutions to target's fast-growing clients"],
                },
                "geographic_synergy": {
                    "score": geo_syn,
                    "explanation": "Fills critical presence in key regional hubs.",
                    "opportunities": ["Establish physical Delivery Center in Europe/US"],
                },
            },
            "technology": {
                "technology_synergy_score": tech_syn,
                "tech_stack_analysis": "Excellent stack compatibility. Built on Python/React hosted on AWS/GCP, matching acquirer infrastructure.",
                "ip_and_patents": ["Proprietary LLM wrapper engine", "Custom dataset preprocessing pipeline"],
                "talent_and_platform_compatibility": f"Target has 25+ senior ML engineers who can immediately step into lead developer roles.",
            },
            "financial": {
                "target_financials": {
                    "revenue": f"${20 + (10 - idx) * 5}M",
                    "ebitda": f"${3 + (10 - idx)}M",
                    "valuation_estimate": f"${15 + (10 - idx) * 6}M – ${25 + (10 - idx) * 9}M",
                    "growth_profile": "+25% YoY",
                },
                "affordability_score": fin_feas,
                "financial_health_score": 8,
                "roi_potential_score": 7,
                "value_creation_score": 8,
                "financial_feasibility": f"Transaction is highly feasible within acquirer's budget of {budget}. Valuation multiple of 8–12x EBITDA is standard for high-growth tech consultancies.",
            },
            "risk": {
                "risk_score": risk_score,
                "strategic_risks": {"level": "Medium" if risk_score > 6 else "Low", "description": "Minor customer overlap could lead to minor contract consolidations."},
                "financial_risks": {"level": "High" if idx == 0 else ("Medium" if risk_score > 4 else "Low"), "description": "Premium multiples could lead to goodwill impairment if integration is delayed."},
                "operational_risks": {"level": "Low", "description": "Operations are standardized on agile workflows, making process integration simple."},
                "technology_risks": {"level": "Low", "description": "Low platform integration friction; standard cloud architectures."},
                "cultural_risks": {"level": "Medium", "description": "Risk of boutique startup talent leaving after earning earn-outs."},
            },
            "devils_advocate": {
                "why_deal_should_not_happen": "Boutique AI consultancies are heavily reliant on 3–4 key founders. If they depart post-acquisition, the value is destroyed.",
                "weak_assumptions": "Assumes immediate 25% cross-sell synergy in year 1, which is historically optimistic for consulting mergers.",
                "value_destruction_scenarios": "Loss of critical technical talent and customer churn due to slower enterprise decision-making under the acquirer's brand.",
                "post_merger_risks": "Cultural clash between corporate hierarchy and startup agility.",
                "competitor_benefits": "Competitors will exploit integration confusion to poach key talent.",
                "bear_case": "Revenue growth flatlines as founders exit, resulting in a $20M write-down within 2 years.",
                "bull_case": "Successful integration allows scaling target's AI IP to 100+ enterprise clients, generating a 3.5× ROI on capital.",
                "cultural_compatibility_score": cult_comp,
            },
            "weighted_synergy_score": weighted,
        })
        task["logs"].append(f"  ✓ {name} — Synergy: {weighted}/100, Risk: {risk_score}/10")

    task["current_agent"] = "M&A Partner Agent"
    task["progress"] = 90
    task["logs"].append("Agent 9 [M&A Partner Agent] reviewing all evaluations...")
    time.sleep(0.8)

    top_evaluations_sorted = sorted(top_evaluations, key=lambda x: x["weighted_synergy_score"], reverse=True)

    recs = []
    for idx, te in enumerate(top_evaluations_sorted):
        if idx == 0:
            tier, rational = "Tier 1", "Highest strategic alignment, strong proprietary AI tools, and manageable risk profile."
        elif idx <= 2:
            tier, rational = "Tier 2", "Excellent capability fit, but slightly higher valuation multiple or integration complexity."
        elif idx <= 5:
            tier, rational = "Tier 3", "Good technology stack, but minor customer overlap or slower growth metrics."
        else:
            tier, rational = "Tier 4", "Low priority; monitor for now as a valuation play."
        recs.append({"company_name": te["profile"]["name"], "tier": tier, "rationalization": rational})

    t0 = top_evaluations_sorted[0]["profile"]["name"]
    t1 = top_evaluations_sorted[1]["profile"]["name"] if len(top_evaluations_sorted) > 1 else t0

    task["results"]["partner"] = {
        "critique": "The analyst models have overstated revenue cross-selling speed. Historical averages suggest integration takes 18 months, not 12. However, the capability fit remains exceptionally strong.",
        "hidden_opportunities": [
            "Leveraging target's pre-trained vertical models to win bids in public sector consulting",
            "Offshore cost arbitrage by moving target backend development to acquirer's delivery centers",
        ],
        "hidden_risks": [
            "Hyperscaler partner status downgrades due to entity consolidation",
            "Key engineer flight post-lockup period (Year 2)",
        ],
        "recommendations_table": recs,
        "final_questions": {
            "Which company should be acquired first?": f"{t0} should be the immediate priority due to its superior AI-agent framework and solid EBITDA margins.",
            "Which acquisition generates maximum shareholder value?": f"{t0} offers the highest ROI, leveraging the acquirer's sales force to scale their proprietary products.",
            "Which acquisition is most feasible?": f"{t1} has a clean corporate structure, transparent valuation expectations, and uses compatible tech stacks.",
            "Which acquisition has the best risk-adjusted return?": f"{t0} presents the lowest risk profile while filling the critical AI engineering capability gap.",
            "What is the ideal acquisition roadmap for the next 3–5 years?": f"Phase 1: Acquire {t0} to build core AI competency. Phase 2: Acquire {t1} in Year 2 for geographic expansion. Phase 3: Roll up smaller regional boutiques in Years 3–5.",
        },
        "ideal_roadmap_milestones": [
            "Month 1–3: Due Diligence & Regulatory Approvals for primary target.",
            "Month 4–6: Legal closing, announcement, and executive alignment workshop.",
            "Month 6–12: Technical integration of proprietary platforms and core systems.",
            "Month 12–24: Cross-selling push across Fortune 500 client base.",
            "Year 2–3: Secondary geographical expansion acquisition.",
            "Year 3–5: Optimization, cost consolidation, and boutique roll-ups.",
        ],
    }

    longlist = []
    rank = 1
    for te in top_evaluations_sorted:
        longlist.append({
            "rank": rank,
            "company": te["profile"]["name"],
            "industry": te["profile"]["industry"],
            "strategic_fit": te["synergies"]["strategic_fit"],
            "synergy_score": te["weighted_synergy_score"],
            "risk_score": te["risk"]["risk_score"],
            "evaluated": True,
        })
        rank += 1
    for c in candidates[10:]:
        longlist.append({
            "rank": rank,
            "company": c["name"],
            "industry": c["industry"],
            "strategic_fit": c["strategic_fit_score"],
            "synergy_score": "N/A",
            "risk_score": "N/A",
            "evaluated": False,
        })
        rank += 1

    task["results"]["longlist"] = longlist
    task["results"]["top_evaluations"] = top_evaluations_sorted

    save_task_to_disk(task_id)
    task["progress"] = 100
    task["status"] = "completed"
    task["logs"].append("✓ Simulated M&A Evaluation completed successfully!")
