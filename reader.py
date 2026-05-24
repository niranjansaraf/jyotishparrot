"""
Gemini API integration for Vedic astrology readings.
"""
import os
from google import genai
from google.genai import types
from datetime import date

_SYSTEM = """You are a classical Jyotish (Vedic astrology) consultant with mastery of the Parashari system.

Your interpretations draw on:
- Vimshottari Dasha system for timing events
- Whole-sign house significations (Bhava lords, natural karakas)
- Planetary dignities: exaltation, debilitation, own-sign, friendly/enemy signs
- Trikona (1,5,9), Kendra (1,4,7,10), Dusthana (6,8,12) house dynamics
- Yoga formations visible in the chart
- Gochar (transits) of Jupiter, Saturn, Rahu/Ketu over natal Moon and Lagna
- Nakshatra qualities and their influence on planetary expression

Tone: grounded, specific, compassionate. Avoid fatalistic language. Give approximate dates
(month/year ranges) for timing. Never use hollow phrases like "the stars suggest" — speak directly
from the chart's evidence. Mention both challenges and opportunities in each period."""


_FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]


def _get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in .env")
    return genai.Client(api_key=api_key)


def _fmt_planet_table(positions: dict, houses: dict, lagna: dict) -> str:
    lines = [
        f"Lagna (Ascendant): {lagna['rashi']} {lagna['degree_in_rashi']:.1f}° | "
        f"Nakshatra: {lagna['nakshatra']} ({lagna['nakshatra_lord']})\n"
    ]
    lines.append(f"{'Planet':<12} {'Rashi':<14} {'Deg':>6} {'House':>5} {'Nakshatra':<22} {'Lord':<10} {'Pada'}")
    lines.append("-" * 85)
    for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]:
        if p not in positions:
            continue
        d = positions[p]
        h = houses.get(p, "?")
        lines.append(
            f"{p:<12} {d['rashi']:<14} {d['degree_in_rashi']:>6.2f}° {h:>5}  "
            f"{d['nakshatra']:<22} {d['nakshatra_lord']:<10} {d['pada']}"
        )
    return "\n".join(lines)


def _fmt_dasha(dasha_info: dict) -> str:
    if not dasha_info:
        return "Dasha data unavailable."
    cm = dasha_info.get("current_mahadasha", {})
    ca = dasha_info.get("current_antardasha", {})
    nm = dasha_info.get("next_mahadasha", {})
    upcoming = dasha_info.get("upcoming_antardashas", [])
    lines = [
        f"Current Mahadasha : {cm.get('planet')} ({cm.get('start_date')} → {cm.get('end_date')})",
        f"Current Antardasha: {ca.get('planet')} ({ca.get('start_date')} → {ca.get('end_date')})",
    ]
    if nm:
        lines.append(f"Next Mahadasha    : {nm.get('planet')} ({nm.get('start_date')} → {nm.get('end_date')})")
    if upcoming:
        lines.append("\nUpcoming Antardashas (within current Mahadasha):")
        for a in upcoming:
            lines.append(f"  {a['planet']:<10} {a['start_date']} → {a['end_date']}")
    return "\n".join(lines)


def _fmt_transits(events: list) -> str:
    if not events:
        return "No major sign ingresses in the next 24 months."
    return "\n".join(
        f"  {e['date']}  {e['planet']} enters {e['to_rashi']} (from {e['from_rashi']})"
        for e in events
    )


def _fmt_panchang(panchang: dict, today: date) -> str:
    p = panchang
    return (
        f"Date  : {today}\n"
        f"Tithi : {p['tithi']} | Paksha: {p['paksha']}\n"
        f"Vara  : {p['vara']}\n"
        f"Naksh : {p['nakshatra']} (lord: {p['nakshatra_lord']})\n"
        f"Yoga  : {p['yoga']} | Karana: {p['karana']}"
    )


def generate_reading(
    name: str,
    birth_date: str,
    birth_time: str,
    birth_city: str,
    positions: dict,
    lagna: dict,
    houses: dict,
    dasha_info: dict,
    panchang: dict,
    transit_events: list,
    ayanamsa: float,
    today: date,
) -> dict:
    chart_text = _fmt_planet_table(positions, houses, lagna)
    dasha_text = _fmt_dasha(dasha_info)
    panchang_text = _fmt_panchang(panchang, today)
    transit_text = _fmt_transits(transit_events)

    prompt = f"""Generate a Jyotish reading for {name}.

Birth: {birth_date} at {birth_time} IST, {birth_city}
Lahiri Ayanamsa: {ayanamsa}°

== NATAL CHART (Sidereal, Whole-Sign Houses) ==
{chart_text}

== VIMSHOTTARI DASHA ==
{dasha_text}

== TODAY'S PANCHANG ==
{panchang_text}

== UPCOMING SLOW-PLANET INGRESSES (next 24 months) ==
{transit_text}

Provide a reading in exactly four sections: Health, Career, Personal Relations, and Guidance.
Ground every point in the natal chart placements, active dasha/antardasha, and upcoming transits.

For the first three sections (Health, Career, Personal Relations) use this exact structure:

One sentence on the overall theme for this life area in the current period.

**Upsides**
- [specific opportunity or strength] — [approximate timeframe, e.g. "mid-2026" or "now through Sep 2026"]
- [specific opportunity or strength] — [approximate timeframe]
- [specific opportunity or strength] — [approximate timeframe]

**Downsides**
- [specific challenge or caution] — [approximate timeframe]
- [specific challenge or caution] — [approximate timeframe]
- [specific challenge or caution] — [approximate timeframe]

For the Guidance section, synthesise the most important challenges from all three areas and give concrete steps the native should take to navigate this period well. Use this exact structure:

One sentence naming the core challenge or opportunity in the current dasha/transit combination.

**Steps to Navigate This Period**
- [Concrete action] — [timeframe and why it is relevant to this chart]
- [Concrete action] — [timeframe and why it is relevant to this chart]
- [Concrete action] — [timeframe and why it is relevant to this chart]
- [Concrete action] — [timeframe and why it is relevant to this chart]
- [Concrete action] — [timeframe and why it is relevant to this chart]

Now write all four sections using this exact format:

## Health
[theme sentence]

**Upsides**
- ...
- ...
- ...

**Downsides**
- ...
- ...
- ...

## Career
[theme sentence]

**Upsides**
- ...
- ...
- ...

**Downsides**
- ...
- ...
- ...

## Personal Relations
[theme sentence]

**Upsides**
- ...
- ...
- ...

**Downsides**
- ...
- ...
- ...

## Guidance
[core challenge/opportunity sentence]

**Steps to Navigate This Period**
- ...
- ...
- ...
- ...
- ...

Be specific to this chart, not generic. Reference house lords, nakshatra qualities, and dasha combinations."""

    client = _get_client()
    preferred = os.getenv("GEMINI_MODEL")
    models_to_try = [preferred] if preferred else _FALLBACK_MODELS

    last_real_err = None
    response = None
    quota_count = 0
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=_SYSTEM),
            )
            break
        except Exception as e:
            kind = _classify_error(e)
            if kind == "missing":
                continue
            last_real_err = e
            if kind == "quota":
                quota_count += 1

    if response is None:
        if last_real_err is None:
            raise RuntimeError("No valid Gemini models found — all returned 404. Check model names in reader.py.")
        if quota_count > 0 and _classify_error(last_real_err) == "quota":
            raise RuntimeError(
                "Daily free-tier quota exhausted for all Gemini models. "
                "Wait a few hours for the quota to reset, or enable billing at "
                "https://ai.dev/rate-limit to get higher limits."
            )
        raise RuntimeError(f"All Gemini models failed. Last error: {last_real_err}")

    full_text = response.text

    def _extract_section(text: str, heading: str) -> str:
        marker = f"## {heading}"
        if marker not in text:
            return ""
        after = text.split(marker, 1)[1]
        # Stop at the next ## heading
        next_heading = after.find("\n## ")
        return after[:next_heading].strip() if next_heading != -1 else after.strip()

    return {
        "health": _extract_section(full_text, "Health"),
        "career": _extract_section(full_text, "Career"),
        "personal_relations": _extract_section(full_text, "Personal Relations"),
        "guidance": _extract_section(full_text, "Guidance"),
        "full_text": full_text,
    }


def translate_reading(sections: dict) -> dict:
    """Translate health / career / personal_relations reading sections to Marathi."""
    prompt = (
        "Translate the following Vedic astrology reading sections from English to Marathi (मराठी).\n\n"
        "Rules:\n"
        "- Preserve all markdown formatting exactly (**, -, bullet points, blank lines).\n"
        "- Do NOT translate these terms — keep them verbatim: Sun, Moon, Mars, Mercury, Jupiter, "
        "Venus, Saturn, Rahu, Ketu, Mahadasha, Antardasha, Vimshottari, Lagna, and all nakshatra "
        "and rashi names (Ashwini, Rohini, Aries, Taurus, etc.).\n"
        "- Keep all dates and timeframes in their original form (e.g. 'mid-2026', 'June 2026').\n"
        "- Translate '**Upsides**' as '**सकारात्मक पैलू**', '**Downsides**' as '**आव्हाने**', "
        "and '**Steps to Navigate This Period**' as '**या काळात मार्गक्रमण करण्याचे उपाय**'.\n"
        "- Use natural, warm Marathi as a knowledgeable Jyotishi would speak to a client.\n\n"
        "Return ONLY the translated sections using exactly these markers (no extra text):\n\n"
        "[HEALTH]\n...translation...\n[/HEALTH]\n\n"
        "[CAREER]\n...translation...\n[/CAREER]\n\n"
        "[PERSONAL_RELATIONS]\n...translation...\n[/PERSONAL_RELATIONS]\n\n"
        "[GUIDANCE]\n...translation...\n[/GUIDANCE]\n\n"
        "=== SECTIONS TO TRANSLATE ===\n\n"
        f"[HEALTH]\n{sections.get('health', '')}\n[/HEALTH]\n\n"
        f"[CAREER]\n{sections.get('career', '')}\n[/CAREER]\n\n"
        f"[PERSONAL_RELATIONS]\n{sections.get('personal_relations', '')}\n[/PERSONAL_RELATIONS]\n\n"
        f"[GUIDANCE]\n{sections.get('guidance', '')}\n[/GUIDANCE]"
    )

    full_text = _call_gemini(prompt)

    def _extract(tag: str) -> str:
        start = full_text.find(f"[{tag}]")
        end   = full_text.find(f"[/{tag}]")
        if start == -1 or end == -1:
            return ""
        return full_text[start + len(f"[{tag}]"):end].strip()

    return {
        "health":            _extract("HEALTH"),
        "career":            _extract("CAREER"),
        "personal_relations": _extract("PERSONAL_RELATIONS"),
        "guidance":          _extract("GUIDANCE"),
    }


def _classify_error(err: Exception):
    """Return 'quota', 'missing', or 'other'."""
    msg = str(err)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        return "quota"
    if "404" in msg or "NOT_FOUND" in msg:
        return "missing"
    return "other"


def _call_gemini(prompt: str) -> str:
    """Shared Gemini call with model fallback."""
    client = _get_client()
    preferred = os.getenv("GEMINI_MODEL")
    models_to_try = [preferred] if preferred else _FALLBACK_MODELS
    last_real_err = None   # first non-404 error seen
    quota_count   = 0
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=_SYSTEM),
            )
            return response.text
        except Exception as e:
            kind = _classify_error(e)
            if kind == "missing":
                continue           # model retired/renamed — try next silently
            last_real_err = e
            if kind == "quota":
                quota_count += 1
    if last_real_err is None:
        raise RuntimeError("No valid Gemini models found — all returned 404. Check model names in reader.py.")
    if quota_count > 0 and _classify_error(last_real_err) == "quota":
        raise RuntimeError(
            "Daily free-tier quota exhausted for all Gemini models. "
            "Wait a few hours for the quota to reset, or enable billing at "
            "https://ai.dev/rate-limit to get higher limits."
        )
    raise RuntimeError(f"All Gemini models failed. Last error: {last_real_err}")


def generate_followup(
    question: str,
    chart_context: str,
    reading_context: str,
    history: list,          # [{"role": "user"|"assistant", "content": "..."}]
) -> str:
    """Answer a follow-up question grounded in the original chart and reading."""
    today_str = date.today().strftime("%B %d, %Y")

    history_block = ""
    if history:
        lines = []
        for msg in history:
            label = "Native" if msg["role"] == "user" else "Astrologer"
            lines.append(f"{label}: {msg['content']}")
        history_block = "\n== PRIOR EXCHANGE ==\n" + "\n\n".join(lines) + "\n"

    prompt = (
        "The following is an ongoing consultation. You have already studied this chart and "
        "delivered the initial reading below. Now the native has a follow-up question.\n\n"
        f"TODAY'S DATE: {today_str}.\n"
        "CRITICAL TIMING RULE: Only reference transits, dasha periods, or planetary positions "
        f"that are active on or after {today_str}. If a transit or period has already ended "
        "before today, do not mention it as current or upcoming — acknowledge it as past if "
        "relevant, or skip it entirely. Ground every timing statement in this anchor date.\n\n"
        f"== CHART SUMMARY ==\n{chart_context}\n\n"
        f"== INITIAL READING (Health / Career / Personal Relations) ==\n{reading_context}\n"
        f"{history_block}\n"
        f"Native's question: {question}\n\n"
        "Answer directly and specifically. Reference the natal chart, active dasha, or transits "
        "where relevant. Keep the response concise (under 250 words) and actionable."
    )
    return _call_gemini(prompt)
