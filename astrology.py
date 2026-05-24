"""
Vedic (Jyotish) astrology calculations using Swiss Ephemeris (NASA JPL DE431 data).
Parashari system: Lahiri ayanamsa, whole-sign houses, Vimshottari Dasha.
"""
import swisseph as swe
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple

# Lahiri ayanamsa — standard for Indian astrology
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

RASHIS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

RASHI_LORDS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
    "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
    "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
}

NAK_SPAN = 360.0 / 27  # ~13.3333°

NAKSHATRAS = [
    ("Ashwini", "Ketu"), ("Bharani", "Venus"), ("Krittika", "Sun"),
    ("Rohini", "Moon"), ("Mrigashira", "Mars"), ("Ardra", "Rahu"),
    ("Punarvasu", "Jupiter"), ("Pushya", "Saturn"), ("Ashlesha", "Mercury"),
    ("Magha", "Ketu"), ("Purva Phalguni", "Venus"), ("Uttara Phalguni", "Sun"),
    ("Hasta", "Moon"), ("Chitra", "Mars"), ("Swati", "Rahu"),
    ("Vishakha", "Jupiter"), ("Anuradha", "Saturn"), ("Jyeshtha", "Mercury"),
    ("Mula", "Ketu"), ("Purva Ashadha", "Venus"), ("Uttara Ashadha", "Sun"),
    ("Shravana", "Moon"), ("Dhanishtha", "Mars"), ("Shatabhisha", "Rahu"),
    ("Purva Bhadrapada", "Jupiter"), ("Uttara Bhadrapada", "Saturn"), ("Revati", "Mercury")
]

DASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
DASHA_YEARS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10,
    "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17
}

PLANET_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
    "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS, "Saturn": swe.SATURN,
    "Rahu": swe.MEAN_NODE
}

TITHI_NAMES = [
    "Pratipada", "Dvitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dvadashi", "Trayodashi", "Chaturdashi", "Purnima"
]

YOGA_NAMES = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana",
    "Atiganda", "Sukarma", "Dhriti", "Shula", "Ganda",
    "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra",
    "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva",
    "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma",
    "Indra", "Vaidhriti"
]

VARA_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def datetime_to_jd(dt: datetime, utc_offset: float = 5.5) -> float:
    """Convert local datetime to Julian Day (UT). Default offset is IST (UTC+5:30)."""
    dt_utc = dt - timedelta(hours=utc_offset)
    return swe.julday(
        dt_utc.year, dt_utc.month, dt_utc.day,
        dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0
    )


def jd_to_date(jd: float) -> date:
    y, m, d, _ = swe.revjul(jd)
    return date(int(y), int(m), int(d))


def _sidereal_lon(jd: float, planet_id: int) -> float:
    flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
    result, _ = swe.calc_ut(jd, planet_id, flags)
    return result[0]


def _tropical_lon(jd: float, planet_id: int) -> float:
    result, _ = swe.calc_ut(jd, planet_id)
    return result[0]


def _nak_info(lon: float) -> Tuple[str, str, int]:
    """Return (nakshatra_name, nakshatra_lord, pada) for a sidereal longitude."""
    idx = int(lon / NAK_SPAN) % 27
    deg_in_nak = lon % NAK_SPAN
    pada = int(deg_in_nak / (NAK_SPAN / 4)) + 1
    name, lord = NAKSHATRAS[idx]
    return name, lord, pada


def get_planet_positions(jd: float) -> Dict[str, dict]:
    """Sidereal positions of all 9 grahas."""
    positions = {}
    for name, pid in PLANET_IDS.items():
        lon = _sidereal_lon(jd, pid)
        rashi_idx = int(lon / 30)
        nak, nak_lord, pada = _nak_info(lon)
        positions[name] = {
            "longitude": round(lon, 3),
            "rashi": RASHIS[rashi_idx],
            "rashi_lord": RASHI_LORDS[RASHIS[rashi_idx]],
            "degree_in_rashi": round(lon % 30, 2),
            "nakshatra": nak,
            "nakshatra_lord": nak_lord,
            "pada": pada,
        }

    # Ketu is always 180° opposite Rahu
    rahu_lon = positions["Rahu"]["longitude"]
    ketu_lon = (rahu_lon + 180) % 360
    rashi_idx = int(ketu_lon / 30)
    nak, nak_lord, pada = _nak_info(ketu_lon)
    positions["Ketu"] = {
        "longitude": round(ketu_lon, 3),
        "rashi": RASHIS[rashi_idx],
        "rashi_lord": RASHI_LORDS[RASHIS[rashi_idx]],
        "degree_in_rashi": round(ketu_lon % 30, 2),
        "nakshatra": nak,
        "nakshatra_lord": nak_lord,
        "pada": pada,
    }
    return positions


def get_lagna(jd: float, lat: float, lon: float) -> dict:
    """Calculate Ascendant (Lagna) in sidereal coordinates."""
    cusps, ascmc = swe.houses(jd, lat, lon, b"W")
    asc_tropical = ascmc[0]
    ayanamsa = swe.get_ayanamsa_ut(jd)
    asc_sidereal = (asc_tropical - ayanamsa) % 360
    rashi_idx = int(asc_sidereal / 30)
    nak, nak_lord, pada = _nak_info(asc_sidereal)
    return {
        "longitude": round(asc_sidereal, 3),
        "rashi": RASHIS[rashi_idx],
        "degree_in_rashi": round(asc_sidereal % 30, 2),
        "nakshatra": nak,
        "nakshatra_lord": nak_lord,
        "pada": pada,
    }


def get_house_positions(lagna_rashi: str, planet_positions: Dict) -> Dict[str, int]:
    """Whole-sign house numbers for each planet (1 = Lagna rashi)."""
    lagna_idx = RASHIS.index(lagna_rashi)
    return {
        planet: ((RASHIS.index(data["rashi"]) - lagna_idx) % 12) + 1
        for planet, data in planet_positions.items()
    }


def get_vimshottari_dasha(moon_lon: float, birth_jd: float) -> List[dict]:
    """Vimshottari Dasha periods starting from the partial dasha at birth."""
    nak_idx = int(moon_lon / NAK_SPAN) % 27
    deg_in_nak = moon_lon % NAK_SPAN
    _, nak_lord = NAKSHATRAS[nak_idx]

    fraction_elapsed = deg_in_nak / NAK_SPAN
    years_elapsed = fraction_elapsed * DASHA_YEARS[nak_lord]
    first_start_jd = birth_jd - years_elapsed * 365.25

    dasha_idx = DASHA_ORDER.index(nak_lord)
    periods = []
    current_jd = first_start_jd

    for _ in range(30):
        planet = DASHA_ORDER[dasha_idx % 9]
        years = DASHA_YEARS[planet]
        end_jd = current_jd + years * 365.25
        periods.append({
            "planet": planet,
            "start_jd": current_jd,
            "end_jd": end_jd,
            "start_date": jd_to_date(current_jd).isoformat(),
            "end_date": jd_to_date(end_jd).isoformat(),
        })
        current_jd = end_jd
        dasha_idx += 1

    return periods


def get_antardasha(maha: dict) -> List[dict]:
    """Nine antardasha sub-periods within a mahadasha."""
    maha_planet = maha["planet"]
    maha_years = DASHA_YEARS[maha_planet]
    maha_idx = DASHA_ORDER.index(maha_planet)
    current_jd = maha["start_jd"]
    periods = []

    for i in range(9):
        planet = DASHA_ORDER[(maha_idx + i) % 9]
        years = (DASHA_YEARS[planet] / 120.0) * maha_years
        end_jd = current_jd + years * 365.25
        periods.append({
            "planet": planet,
            "start_jd": current_jd,
            "end_jd": end_jd,
            "start_date": jd_to_date(current_jd).isoformat(),
            "end_date": jd_to_date(end_jd).isoformat(),
        })
        current_jd = end_jd

    return periods


def get_current_dasha_info(dasha_periods: List[dict], today_jd: float) -> dict:
    """Find the active mahadasha and antardasha for today."""
    current_maha = next_maha = None

    for i, p in enumerate(dasha_periods):
        if p["start_jd"] <= today_jd < p["end_jd"]:
            current_maha = p
            next_maha = dasha_periods[i + 1] if i + 1 < len(dasha_periods) else None
            break

    if not current_maha:
        return {}

    antardashas = get_antardasha(current_maha)
    current_antar = next_antar = None

    for i, a in enumerate(antardashas):
        if a["start_jd"] <= today_jd < a["end_jd"]:
            current_antar = a
            next_antar = antardashas[i + 1] if i + 1 < len(antardashas) else None
            break

    upcoming_antar = [a for a in antardashas if a["start_jd"] > today_jd]

    return {
        "current_mahadasha": current_maha,
        "next_mahadasha": next_maha,
        "current_antardasha": current_antar,
        "next_antardasha": next_antar,
        "upcoming_antardashas": upcoming_antar[:6],
    }


def get_panchang(today_jd: float) -> dict:
    """Five panchang elements for today (uses tropical Sun/Moon for Tithi/Yoga)."""
    sun_trop = _tropical_lon(today_jd, swe.SUN)
    moon_trop = _tropical_lon(today_jd, swe.MOON)

    # Tithi: every 12° of Moon-Sun elongation = 1 tithi
    elongation = (moon_trop - sun_trop) % 360
    tithi_num = int(elongation / 12) + 1  # 1..30
    paksha = "Shukla (Waxing)" if tithi_num <= 15 else "Krishna (Waning)"
    display_num = tithi_num if tithi_num <= 15 else tithi_num - 15
    tithi_name = TITHI_NAMES[min(display_num - 1, 14)]
    if tithi_num == 15:
        tithi_name = "Purnima"
    elif tithi_num == 30:
        tithi_name = "Amavasya"

    # Vara (weekday) — JD 0.5 = Monday noon
    vara_idx = (int(today_jd + 1.5)) % 7
    vara = VARA_NAMES[vara_idx]

    # Moon nakshatra (sidereal)
    moon_sid = _sidereal_lon(today_jd, swe.MOON)
    nak_idx = int(moon_sid / NAK_SPAN) % 27
    moon_nak, moon_nak_lord = NAKSHATRAS[nak_idx]

    # Yoga: (Sun + Moon tropical) / NAK_SPAN
    yoga_lon = (sun_trop + moon_trop) % 360
    yoga_idx = int(yoga_lon / NAK_SPAN) % 27
    yoga = YOGA_NAMES[yoga_idx]

    # Karana: every 6° of elongation = 1 karana
    karana_idx = int(elongation / 6)
    fixed_karanas = ["Kimstughna", "Bava", "Balava", "Kaulava", "Taitula",
                     "Garaja", "Vanija", "Vishti", "Bava", "Balava", "Kaulava"]
    karana = fixed_karanas[karana_idx % 11]

    return {
        "tithi": f"{tithi_name} ({tithi_num})",
        "paksha": paksha,
        "vara": vara,
        "nakshatra": moon_nak,
        "nakshatra_lord": moon_nak_lord,
        "yoga": yoga,
        "karana": karana,
    }


def get_upcoming_transit_events(today_jd: float, months: int = 24) -> List[dict]:
    """Track sign changes of Jupiter, Saturn, Rahu — sampled every 15 days."""
    events = []
    end_jd = today_jd + months * 30.44
    slow_planets = {"Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE}

    for planet, pid in slow_planets.items():
        current_rashi = None
        jd = today_jd
        while jd < end_jd:
            lon = _sidereal_lon(jd, pid)
            rashi_idx = int(lon / 30) % 12
            rashi = RASHIS[rashi_idx]
            if current_rashi is None:
                current_rashi = rashi
            elif rashi != current_rashi:
                events.append({
                    "planet": planet,
                    "from_rashi": current_rashi,
                    "to_rashi": rashi,
                    "date": jd_to_date(jd).isoformat(),
                })
                current_rashi = rashi
            jd += 15

    events.sort(key=lambda x: x["date"])
    return events


def get_ayanamsa(jd: float) -> float:
    return round(swe.get_ayanamsa_ut(jd), 4)
