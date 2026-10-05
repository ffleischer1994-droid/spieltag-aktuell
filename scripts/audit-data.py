#!/usr/bin/env python3
import argparse, datetime as dt, json, re, sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent.parent
ALLOWED_GROUPS={"free","dazn","sky","prime","other"}
PRIORITY_RX=re.compile(r"Bundesliga|2\. Bundesliga|3\. Liga|DFB-Pokal|Champions League|Europa League|Conference League|Nations League|Deutschland",re.I)
WOMEN_RX=re.compile(r"♀|Frauen|Women|Femminile",re.I)

def is_priority(g):
    text=" ".join(str(g.get(k,"")) for k in ("home","away","competition","country"))
    return g.get("country")=="Deutschland" or bool(PRIORITY_RX.search(text))

def is_women(g):
    return bool(WOMEN_RX.search(" ".join(str(g.get(k,"")) for k in ("home","away","competition"))))

def pct(a,b):
    return 100.0*a/b if b else 100.0

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--today")
    ap.add_argument("--report",default="data-quality-report.md")
    args=ap.parse_args()
    today=dt.date.fromisoformat(args.today) if args.today else dt.datetime.now(ZoneInfo("Europe/Berlin")).date()
    end=today+dt.timedelta(days=6)

    data=json.loads((ROOT/"games.json").read_text())
    errors=[]
    warnings=[]
    required={"date","time","home","away","competition","country","channels","groups"}
    exact=set()
    pair_times={}
    keys=[]

    for i,g in enumerate(data):
        missing=required-set(g)
        if missing:
            errors.append(f"Zeile {i}: Pflichtfelder fehlen: {sorted(missing)}")
            continue
        try: dt.date.fromisoformat(g["date"])
        except Exception: errors.append(f"Zeile {i}: ungültiges Datum {g.get('date')!r}")
        try: dt.time.fromisoformat(g["time"])
        except Exception: errors.append(f"Zeile {i}: ungültige Uhrzeit {g.get('time')!r}")

        for field in ("home","away","competition","country"):
            if not isinstance(g.get(field),str) or not g[field].strip():
                errors.append(f"Zeile {i}: {field} ist leer/ungültig")

        if not isinstance(g.get("channels"),list) or not g["channels"]:
            errors.append(f"Zeile {i}: keine Sender")
        elif len(g["channels"])!=len(set(g["channels"])):
            errors.append(f"Zeile {i}: doppelte Sender")

        groups=g.get("groups")
        if not isinstance(groups,list) or not groups:
            errors.append(f"Zeile {i}: groups leer/ungültig")
        else:
            unknown=set(groups)-ALLOWED_GROUPS
            if unknown: errors.append(f"Zeile {i}: unbekannte groups {sorted(unknown)}")

        channel_text=" ".join(g.get("channels",[]))
        if re.search(r"DAZN",channel_text,re.I) and "dazn" not in groups:
            errors.append(f"Zeile {i}: DAZN-Sender ohne group=dazn")
        german_sky=any(
            re.search(r"Sky|WOW",c,re.I)
            and not re.search(r"\((?:AT|CH|Austria|Schweiz)\)|Sky Sport Austria",c,re.I)
            for c in g.get("channels",[])
        )
        if german_sky and "sky" not in groups:
            errors.append(f"Zeile {i}: deutscher Sky/WOW-Sender ohne group=sky")
        if re.search(r"Prime",channel_text,re.I) and "prime" not in groups:
            warnings.append(f"Zeile {i}: Prime-Sender ohne group=prime")

        key=(g["date"],g["time"],g["home"],g["away"])
        if key in exact: errors.append("Doppelte Partie: "+" | ".join(key))
        exact.add(key)
        pair=(g["date"],g["home"],g["away"])
        pair_times.setdefault(pair,set()).add(g["time"])
        keys.append(key)

        for s in g.get("sources",[]) or []:
            if not isinstance(s,dict) or not str(s.get("url","")).startswith("https://"):
                errors.append(f"{g['date']} {g['home']} – {g['away']}: ungültige Quelle")
        for name,u in (g.get("channelLinks") or {}).items():
            if not str(u).startswith("https://"):
                errors.append(f"{g['date']} {g['home']} – {g['away']}: unsicherer Senderlink {name}")

        if g.get("verifiedAt"):
            try: dt.datetime.fromisoformat(g["verifiedAt"].replace("Z","+00:00"))
            except Exception: errors.append(f"{g['date']} {g['home']} – {g['away']}: verifiedAt ungültig")

    for pair,times in pair_times.items():
        if len(times)>1:
            errors.append("Widersprüchliche Uhrzeiten: "+" | ".join(pair)+" => "+", ".join(sorted(times)))

    expected=sorted(keys)
    if keys!=expected:
        errors.append("games.json ist nicht strikt nach Datum, Uhrzeit, Heim- und Auswärtsteam sortiert")

    window=[g for g in data if today.isoformat()<=g.get("date","")<=end.isoformat()]
    today_rows=[g for g in window if g.get("date")==today.isoformat()]
    if not today_rows:
        errors.append(f"Keine Spiele für heute ({today.isoformat()}) im 7-Tage-Datenfenster")

    priority=[g for g in window if is_priority(g)]
    women=[g for g in window if is_women(g)]
    sourced=[g for g in priority if g.get("sources") or g.get("verifiedAt")]
    women_sourced=[g for g in women if g.get("sources") or g.get("verifiedAt")]

    missing_priority=[g for g in priority if not (g.get("sources") or g.get("verifiedAt"))]
    missing_women=[g for g in women if not (g.get("sources") or g.get("verifiedAt"))]

    report=[
        "# Spieltag Aktuell – Datenqualitätsbericht",
        "",
        f"- Prüfdatum: {today.strftime('%d.%m.%Y')}",
        f"- Datenfenster: {today.strftime('%d.%m.%Y')}–{end.strftime('%d.%m.%Y')}",
        f"- Spiele im Fenster: **{len(window)}**",
        f"- Spiele heute: **{len(today_rows)}**",
        f"- DE-/Top-Relevanz: **{len(priority)}**, davon mit Quelle/Verifikation: **{len(sourced)} ({pct(len(sourced),len(priority)):.0f} %)**",
        f"- Frauenfußball: **{len(women)}**, davon mit Quelle/Verifikation: **{len(women_sourced)} ({pct(len(women_sourced),len(women)):.0f} %)**",
        "",
    ]
    if missing_priority:
        report += ["## Noch ohne dokumentierte Quelle/Verifikation (Priorität)", ""]
        for g in missing_priority[:40]:
            report.append(f"- {g['date']} {g['time']} · {g['home']} – {g['away']} · {g['competition']}")
        if len(missing_priority)>40: report.append(f"- … plus {len(missing_priority)-40} weitere")
        report.append("")
    if missing_women:
        report += ["## Frauenfußball ohne dokumentierte Quelle/Verifikation", ""]
        for g in missing_women[:30]:
            report.append(f"- {g['date']} {g['time']} · {g['home']} – {g['away']} · {g['competition']}")
        if len(missing_women)>30: report.append(f"- … plus {len(missing_women)-30} weitere")
        report.append("")
    if warnings:
        report += ["## Warnungen", ""]+[f"- {w}" for w in warnings]+[""]
    if errors:
        report += ["## Harte Fehler", ""]+[f"- {e}" for e in errors]+[""]
    else:
        report += ["## Harte Fehler", "", "- Keine.", ""]

    Path(args.report).write_text("\n".join(report)+"\n")
    print("\n".join(report))
    if errors: return 1
    return 0

if __name__=="__main__":
    raise SystemExit(main())
