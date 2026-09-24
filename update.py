#!/usr/bin/env python3
"""
Holt Pegelstaende und Niederschlagsprognose und schreibt daten.json.

Pegel: PEGELONLINE (Wasserstrassen- und Schifffahrtsverwaltung des Bundes).
       Verwendet wird der 05:00-Wert Ortszeit, verglichen mit dem 05:00-Wert
       des Vortags.
Regen: MET Norway (Meteorologisches Institut Norwegen), Tagessummen.

Laeuft ohne Zugangsdaten - beide Quellen sind offen.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")

# MET Norway verlangt eine Kennung mit Kontaktmoeglichkeit.
USER_AGENT = "varuna-fahrwasser/1.0 (info@renship.de)"

PEGEL = [
    {"id": "MAXAU",    "name": "Maxau",     "river": "Rhein"},
    {"id": "MANNHEIM", "name": "Mannheim",  "river": "Rhein"},
    {"id": "MAINZ",    "name": "Mainz",     "river": "Rhein"},
    {"id": "KAUB",     "name": "Kaub",      "river": "Rhein"},
]

GEBIETE = [
    {"name": "Alpenrheintal / Vorarlberg", "lat": 47.50, "lon": 9.75},
    {"name": "Schwarzwald, Hochlagen",     "lat": 47.87, "lon": 8.00},
    {"name": "Oberrhein / Pfalz",          "lat": 49.21, "lon": 8.12},
]

PO = "https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations"
MET = "https://api.met.no/weatherapi/locationforecast/2.0/compact"


def cm(wert):
    """Kaufmaennisch auf ganze Zentimeter runden (Pythons round() rundet .5
    abwechselnd auf und ab, was bei Pegelwerten irritiert)."""
    import math
    return int(math.floor(float(wert) + 0.5))


def hole(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fuenf_uhr_werte(station_id):
    """Liefert (heute_05, gestern_05) als cm-Werte, jeweils None wenn nicht da."""
    reihe = hole(f"{PO}/{station_id}/W/measurements.json?start=P3D")

    heute = datetime.now(TZ).date()
    gestern = heute - timedelta(days=1)
    treffer = {}

    for punkt in reihe:
        try:
            ts = datetime.fromisoformat(punkt["timestamp"]).astimezone(TZ)
        except (KeyError, ValueError):
            continue
        if ts.hour == 5 and ts.minute == 0 and ts.date() in (heute, gestern):
            treffer[ts.date()] = (punkt.get("value"), ts)

    h = treffer.get(heute)
    g = treffer.get(gestern)
    return h, g


def zustand(station_id):
    try:
        return hole(f"{PO}/{station_id}/W/currentmeasurement.json").get("stateMnwMhw")
    except Exception:
        return None


def pegel_block():
    items = []
    for p in PEGEL:
        eintrag = {
            "id": p["id"], "name": p["name"], "river": p["river"],
            "value": None, "ts": None, "state": None,
            "trend": "unknown", "trendNote": "", "placeholder": False,
        }
        try:
            heute, gestern = fuenf_uhr_werte(p["id"])
        except Exception as e:
            eintrag["trendNote"] = "Quelle nicht erreichbar"
            print(f"  {p['name']}: Fehler beim Abruf: {e}", file=sys.stderr)
            items.append(eintrag)
            continue

        if heute:
            wert, ts = heute
            eintrag["value"] = cm(wert)
            eintrag["ts"] = ts.isoformat()
        elif gestern:
            wert, ts = gestern
            eintrag["value"] = cm(wert)
            eintrag["ts"] = ts.isoformat()
            eintrag["trendNote"] = "heutiger 5-Uhr-Wert fehlt noch"

        if heute and gestern:
            h, g = cm(heute[0]), cm(gestern[0])
            eintrag["trend"] = "rising" if h > g else "falling" if h < g else "steady"
            eintrag["trendNote"] = f"5-Uhr-Werte: {g} → {h} cm seit gestern"

        eintrag["state"] = zustand(p["id"])
        items.append(eintrag)
        print(f"  {p['name']}: {eintrag['value']} cm, {eintrag['trend']}")

    return {
        "updatedAt": datetime.now(TZ).isoformat(timespec="minutes"),
        "placeholder": False,
        "items": items,
    }


def tagessummen(lat, lon):
    """
    Summiert den Niederschlag je Kalendertag.

    Jeder Zeitpunkt kann next_1_hours, next_6_hours und next_12_hours tragen -
    die ueberlappen sich. Pro Zeitpunkt wird deshalb genau ein Zeitraum
    gezaehlt: bevorzugt der Einstundenwert, sonst der Sechsstundenwert.
    next_12_hours bleibt immer aussen vor.
    """
    daten = hole(f"{MET}?lat={lat}&lon={lon}")
    summen = {}

    for eintrag in daten["properties"]["timeseries"]:
        ts = datetime.fromisoformat(eintrag["time"].replace("Z", "+00:00")).astimezone(TZ)
        zeitraum = eintrag.get("data", {}).get("next_1_hours") \
            or eintrag.get("data", {}).get("next_6_hours")
        if not zeitraum:
            continue
        mm = zeitraum.get("details", {}).get("precipitation_amount")
        if mm is None:
            continue
        summen[ts.date()] = summen.get(ts.date(), 0.0) + mm

    heute = datetime.now(TZ).date()
    return [round(summen.get(heute + timedelta(days=i), 0.0)) for i in range(7)]


def regen_block():
    gebiete = []
    for g in GEBIETE:
        try:
            mm = tagessummen(g["lat"], g["lon"])
            print(f"  {g['name']}: {mm}")
        except Exception as e:
            print(f"  {g['name']}: Fehler beim Abruf: {e}", file=sys.stderr)
            return None
        gebiete.append({"name": g["name"], "mm": mm})

    return {
        "updatedAt": datetime.now(TZ).isoformat(timespec="minutes"),
        "placeholder": False,
        "areas": gebiete,
    }


# --- Diesel-Schaetzung -------------------------------------------------------
# Angepasst an zwoelf Rheintank-Rechnungen (Januar bis August 2026) gegen den
# US-Heizoel-Future, umgerechnet in Euro je 100 Liter. Bestimmtheitsmass 0,85,
# mittlerer Fehler rund 6 Euro. Die Belege selbst liegen NICHT in diesem
# Repository - hier steht nur das Ergebnis der Anpassung.
MODELL_A = 1.3479
MODELL_B = -11.742
MODELL_RMSE = 7.7

YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/"
GALLONE_L = 3.785411784


def yahoo_reihe(symbol, tage=120):
    """Schlusskurse je Handelstag als {datum: wert}."""
    jetzt = int(datetime.now(TZ).timestamp())
    von = jetzt - tage * 86400
    url = (f"{YAHOO}{urllib.parse.quote(symbol)}"
           f"?period1={von}&period2={jetzt}&interval=1d")
    roh = hole(url)["chart"]["result"][0]
    stempel = roh.get("timestamp") or []
    schluss = roh["indicators"]["quote"][0].get("close") or []
    reihe = {}
    for t, v in zip(stempel, schluss):
        if v is not None:
            reihe[datetime.fromtimestamp(t, TZ).date().isoformat()] = v
    return reihe


def diesel_block():
    try:
        heizoel = yahoo_reihe("HO=F")
        kurs = yahoo_reihe("EURUSD=X")
    except Exception as e:
        print(f"  Marktdaten nicht erreichbar: {e}", file=sys.stderr)
        return None

    tage = sorted(set(heizoel) & set(kurs))
    if not tage:
        print("  Keine gemeinsamen Handelstage gefunden.", file=sys.stderr)
        return None

    verlauf = []
    for t in tage:
        roh = heizoel[t] / kurs[t] / GALLONE_L * 100      # Euro je 100 Liter
        verlauf.append({"d": t, "v": round(MODELL_A * roh + MODELL_B, 1)})

    letzter = tage[-1]
    schaetzung = verlauf[-1]["v"]
    print(f"  Diesel geschaetzt: {schaetzung} EUR/100L (Marktstand {letzter})")

    return {
        "updatedAt": datetime.now(TZ).isoformat(timespec="minutes"),
        "placeholder": False,
        "estimate": schaetzung,
        "low": round(schaetzung - MODELL_RMSE),
        "high": round(schaetzung + MODELL_RMSE),
        "marketDate": letzter,
        "heizoelUsdGal": round(heizoel[letzter], 4),
        "eurUsd": round(kurs[letzter], 4),
        "history": verlauf[-45:],
        "model": {"a": MODELL_A, "b": MODELL_B, "r2": 0.853,
                  "n": 12, "rmse": MODELL_RMSE},
    }


def vorheriges(schluessel):
    """Alten Stand aus daten.json holen, damit eine Kachel nie leer wird."""
    try:
        with open("daten.json", encoding="utf-8") as f:
            return json.load(f).get(schluessel)
    except Exception:
        return None


def main():
    print("Pegel:")
    gauges = pegel_block()

    print("Niederschlag:")
    rain = regen_block()

    if rain is None:
        # Lieber den alten Regenstand behalten als die Kachel leeren.
        rain = vorheriges("rain") or {"updatedAt": None, "placeholder": True,
                                      "areas": []}
        print("  Wetterquelle nicht erreichbar, vorheriger Stand bleibt stehen.",
              file=sys.stderr)

    print("Diesel:")
    diesel = diesel_block()
    if diesel is None:
        diesel = vorheriges("diesel")
        print("  Marktquelle nicht erreichbar, vorheriger Stand bleibt stehen.",
              file=sys.stderr)

    if all(i["value"] is None for i in gauges["items"]):
        print("Kein einziger Pegelwert abrufbar - daten.json bleibt unveraendert.",
              file=sys.stderr)
        return 1

    ergebnis = {"gauges": gauges, "rain": rain}
    if diesel:
        ergebnis["diesel"] = diesel

    with open("daten.json", "w", encoding="utf-8") as f:
        json.dump(ergebnis, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print("daten.json geschrieben.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
