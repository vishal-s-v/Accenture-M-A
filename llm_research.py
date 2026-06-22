"""
LLM Research layer — queries OpenAI or Google Gemini for company intelligence.
Keys are read from config.py. Only one provider is required.
Prompts are intentionally minimal to keep token usage low.
"""

import json
from typing import Dict, Any, Optional, List

try:
    from openai import OpenAI
    _OPENAI_OK = True
except ImportError:
    _OPENAI_OK = False

try:
    from google import genai as _google_genai
    _GEMINI_OK = True
except ImportError:
    _GEMINI_OK = False

# ── Minimal company facts prompt (~120 tokens in, ~200 tokens out) ────────────
_COMPANY_PROMPT = """\
Return JSON only. Company: "{company}"
Keys required (null if unknown):
hq, founded, employees, revenue, sector, services(list<=6), clients(list<=5), executives(list of {{name,title}}<=3), news(list<=3 headlines)"""

# ── Minimal discovery prompt (~150 tokens in, ~250 tokens out) ───────────────
_DISCOVERY_PROMPT = """\
Return JSON only. Find acquisition targets for "{acquirer}".
Thesis: sector={sector}, geography={geography}, capability={capability_gap}, revenue={revenue_range}
Keys: targets(list of {{name,hq,revenue,rationale}}<=5)
Only real companies you are confident exist."""


def _call_openai(prompt: str, api_key: str, model: str = "gpt-4o-mini") -> Optional[Dict]:
    if not _OPENAI_OK or not api_key:
        return None
    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content or "{}")
    except Exception as e:
        print(f"[llm_research] OpenAI error: {e}")
        return None


def _call_gemini(prompt: str, api_key: str, model: str = "gemini-2.0-flash") -> Optional[Dict]:
    if not _GEMINI_OK or not api_key:
        return None
    try:
        client = _google_genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config=_google_genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=400,
                temperature=0,
            ),
        )
        return json.loads(resp.text or "{}")
    except Exception as e:
        print(f"[llm_research] Gemini error: {e}")
        return None


def _call_llm(prompt: str, openai_key: str, gemini_key: str) -> Optional[Dict]:
    """Try OpenAI first, fall back to Gemini."""
    if openai_key:
        result = _call_openai(prompt, openai_key)
        if result:
            return result, "OpenAI"
    if gemini_key:
        result = _call_gemini(prompt, gemini_key)
        if result:
            return result, "Gemini"
    return None, None


def _safe_list(v: Any, limit: int = 6) -> List:
    if isinstance(v, list):
        return [str(x) for x in v[:limit] if x]
    return []


def research_company(
    company_name: str,
    openai_key: str = "",
    gemini_key: str = "",
) -> Dict[str, Any]:
    """Query one LLM for minimal company facts. Returns context string + raw data."""
    if not openai_key and not gemini_key:
        return {}

    prompt = _COMPANY_PROMPT.format(company=company_name)
    raw, source = _call_llm(prompt, openai_key, gemini_key)
    if not raw:
        return {}

    # Normalise to only the fields we actually use downstream
    collated = {
        "hq":        raw.get("hq"),
        "founded":   raw.get("founded"),
        "employees": raw.get("employees"),
        "revenue":   raw.get("revenue"),
        "sector":    raw.get("sector"),
        "services":  _safe_list(raw.get("services")),
        "clients":   _safe_list(raw.get("clients")),
        "executives": [
            {"name": e.get("name",""), "title": e.get("title","")}
            for e in (raw.get("executives") or [])[:3]
            if isinstance(e, dict)
        ],
        "news":      _safe_list(raw.get("news"), 3),
    }

    lines = [f"[{source.upper()} RESEARCH]"]
    for k, label in [("hq","HQ"), ("founded","Founded"), ("employees","Employees"),
                     ("revenue","Revenue"), ("sector","Sector")]:
        if collated.get(k):
            lines.append(f"  {label}: {collated[k]}")
    if collated["services"]:
        lines.append(f"  Services: {', '.join(collated['services'])}")
    if collated["clients"]:
        lines.append(f"  Clients: {', '.join(collated['clients'])}")
    if collated["executives"]:
        execs = ", ".join(f"{e['name']} ({e['title']})" for e in collated["executives"])
        lines.append(f"  Executives: {execs}")
    if collated["news"]:
        lines.append(f"  News: {' | '.join(collated['news'])}")

    return {
        "collated":     collated,
        "sources_used": [source],
        "context_str":  "\n".join(lines),
    }


def research_discovery_targets(
    acquirer: str,
    thesis: Dict[str, str],
    openai_key: str = "",
    gemini_key: str = "",
) -> Dict[str, Any]:
    """Ask one LLM for acquisition target suggestions."""
    if not openai_key and not gemini_key:
        return {}

    prompt = _DISCOVERY_PROMPT.format(
        acquirer=acquirer,
        sector=thesis.get("sector", ""),
        geography=thesis.get("geography", ""),
        capability_gap=thesis.get("capability_gap", ""),
        revenue_range=thesis.get("revenue_range", "$50M-$500M"),
    )
    raw, source = _call_llm(prompt, openai_key, gemini_key)
    if not raw:
        return {}

    targets = []
    for t in (raw.get("targets") or [])[:5]:
        if isinstance(t, dict) and t.get("name"):
            targets.append({
                "name":     t.get("name", ""),
                "hq":       t.get("hq", ""),
                "revenue":  t.get("revenue", ""),
                "rationale":t.get("rationale", ""),
            })

    lines = [f"[{source.upper()} DISCOVERY]"]
    for t in targets:
        lines.append(f"  {t['name']} | HQ: {t['hq']} | Rev: {t['revenue']} | {t['rationale']}")

    return {
        "collated":     {"targets": targets},
        "sources_used": [source],
        "context_str":  "\n".join(lines),
        "target_names": [t["name"] for t in targets],
    }
