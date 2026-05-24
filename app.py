"""
Jyotish — Vedic Astrology Agent
Flask web app: takes birth details, computes natal chart + Vimshottari Dasha,
then calls Gemini for a Parashari reading.
"""
import os
import socket
import sqlite3
import uuid
import json
import urllib.request
import urllib.parse
from datetime import datetime, date
from pathlib import Path

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

from cities import CITIES


def _get_lan_ip() -> str:
    """Return the machine's LAN IP (the address other devices on the same Wi-Fi see)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()
import astrology as ast
import reader

app = Flask(__name__)

# ── Persistent reading storage ─────────────────────────────────
# DATA_DIR can be overridden via env var to point at a Railway Volume (/data)
_DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parent))
_DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = _DATA_DIR / "readings.db"

def _init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS readings (
            id   TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

_init_db()


@app.route("/")
def index():
    cities = sorted(CITIES.keys())
    return render_template("index.html", cities=cities)


@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json()
        name = data.get("name", "").strip() or "Native"
        dob = data["dob"]          # "YYYY-MM-DD"
        tob = data["tob"]          # "HH:MM"
        city = data.get("city", "")

        # Resolve coordinates
        if city and city in CITIES:
            lat, lon = CITIES[city]
        else:
            lat = float(data.get("lat", 12.9716))
            lon = float(data.get("lon", 77.5946))

        # Parse datetime (IST)
        birth_dt = datetime.strptime(f"{dob} {tob}", "%Y-%m-%d %H:%M")
        birth_jd = ast.datetime_to_jd(birth_dt, utc_offset=5.5)

        # Today
        now = datetime.utcnow()
        today_jd = ast.datetime_to_jd(now, utc_offset=0)
        today = date.today()

        # --- Chart calculations ---
        positions = ast.get_planet_positions(birth_jd)
        lagna = ast.get_lagna(birth_jd, lat, lon)
        houses = ast.get_house_positions(lagna["rashi"], positions)
        ayanamsa = ast.get_ayanamsa(birth_jd)

        moon_lon = positions["Moon"]["longitude"]
        dasha_periods = ast.get_vimshottari_dasha(moon_lon, birth_jd)
        dasha_info = ast.get_current_dasha_info(dasha_periods, today_jd)

        panchang = ast.get_panchang(today_jd)
        transit_events = ast.get_upcoming_transit_events(today_jd, months=24)

        # --- Claude reading ---
        if not os.getenv("GEMINI_API_KEY"):
            return jsonify({"error": "GEMINI_API_KEY not set. Add it to your .env file."}), 500

        reading = reader.generate_reading(
            name=name,
            birth_date=dob,
            birth_time=tob,
            birth_city=city or f"{lat:.4f}N, {lon:.4f}E",
            positions=positions,
            lagna=lagna,
            houses=houses,
            dasha_info=dasha_info,
            panchang=panchang,
            transit_events=transit_events,
            ayanamsa=ayanamsa,
            today=today,
        )

        # Serialize dates in dasha_info for JSON
        def serialize_dasha(d):
            if not d:
                return d
            return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in d.items()}

        return jsonify({
            "lagna": lagna,
            "positions": positions,
            "houses": houses,
            "ayanamsa": ayanamsa,
            "dasha_info": {
                "current_mahadasha": dasha_info.get("current_mahadasha"),
                "next_mahadasha": dasha_info.get("next_mahadasha"),
                "current_antardasha": dasha_info.get("current_antardasha"),
                "next_antardasha": dasha_info.get("next_antardasha"),
                "upcoming_antardashas": dasha_info.get("upcoming_antardashas", []),
            },
            "panchang": panchang,
            "transit_events": transit_events,
            "reading": reading,
        })

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/save", methods=["POST"])
def save_reading():
    try:
        payload = request.get_json()
        rid = str(uuid.uuid4())[:8]
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO readings (id, data) VALUES (?, ?)",
                         (rid, json.dumps(payload)))

        # Use the machine's LAN IP so the link opens on other devices (mobile, etc.)
        host = request.host  # e.g. "localhost:5000" or "127.0.0.1:5000"
        hostname, _, port_str = host.partition(":")
        if hostname in ("localhost", "127.0.0.1"):
            hostname = _get_lan_ip()
        base = f"http://{hostname}:{port_str}" if port_str else f"http://{hostname}"
        long_url = f"{base}/r/{rid}"

        # Try TinyURL (works for IPs/hostnames; not for localhost)
        short_url = long_url
        try:
            encoded = urllib.parse.quote(long_url, safe="")
            resp = urllib.request.urlopen(
                f"https://tinyurl.com/api-create.php?url={encoded}", timeout=5
            )
            candidate = resp.read().decode().strip()
            if candidate.startswith("http"):
                short_url = candidate
        except Exception:
            pass

        return jsonify({"id": rid, "url": long_url, "short_url": short_url})

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/r/<rid>")
def view_reading(rid):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT data FROM readings WHERE id = ?", (rid,)).fetchone()
    if not row:
        return render_template("not_found.html"), 404
    data = json.loads(row[0])
    return render_template("share.html", data=data)


@app.route("/followup", methods=["POST"])
def followup():
    try:
        if not os.getenv("GEMINI_API_KEY"):
            return jsonify({"error": "GEMINI_API_KEY not set."}), 500

        data = request.get_json()
        question       = (data.get("question") or "").strip()
        chart_context  = data.get("chart_context", "")
        reading_context = data.get("reading_context", "")
        history        = data.get("history", [])

        if not question:
            return jsonify({"error": "No question provided."}), 400

        answer = reader.generate_followup(
            question=question,
            chart_context=chart_context,
            reading_context=reading_context,
            history=history,
        )
        return jsonify({"answer": answer})

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/translate", methods=["POST"])
def translate():
    try:
        if not os.getenv("GEMINI_API_KEY"):
            return jsonify({"error": "GEMINI_API_KEY not set."}), 500
        data = request.get_json()
        result = reader.translate_reading({
            "health": data.get("health", ""),
            "career": data.get("career", ""),
            "personal_relations": data.get("personal_relations", ""),
            "guidance": data.get("guidance", ""),
        })
        return jsonify(result)
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    lan_ip = _get_lan_ip()
    print(f"\n✦ Jyotish")
    print(f"  Local  → http://localhost:{port}")
    print(f"  Mobile → http://{lan_ip}:{port}  ← open this on your phone\n")
    app.run(debug=True, host="0.0.0.0", port=port)
