#!/usr/bin/env python3
"""Compare the current day's published fixtures with fussballgucken.info.

This is an audit, not an automatic importer: source discrepancies are reported
so an authoritative club/league/provider source can decide the correction.
"""
import argparse, datetime as dt, html as htmlmod, json, re, sys, unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent.parent
BASE="https://fussballgucken.info"

def norm(value):
    value=htmlmod.unescape(str(value or "")).replace("♀"," frauen ")
    value=unicodedata.normalize("NFKD",value).encode("ascii","ignore").decode().lower()
    value=value.replace("ß","ss")
    value=re.sub(r"\b(?:e\.?v\.?|u23|u21)\b"," ",value)
    return re.sub(r"[^a-z0-9]+"," ",value).strip()

def team_similarity(a,b):
    aa=set(norm(a).split());bb=set(norm(b).split())
    if not aa or not bb:return 0.0
    if norm(a)==norm(b):return 1.0
    return len(aa&bb)/max(len(aa),len(bb))

def pair_score(src,local):
    direct=(team_similarity(src["home"],local["home"])+team_similarity(src["away"],local["away"]))/2
    reverse=(team_similarity(src["home"],local["away"])+team_similarity(src["away"],local["home"]))/2
    return max(direct,reverse)

def fetch(session,url):
    r=session.get(url,timeout=20,headers={"User-Agent":"SpieltagAktuell/1.0 (+https://spieltagaktuell.de/datenquellen/)"})
    r.raise_for_status()
    return r.text

def parse_match(session,url,date):
    try:
        soup=BeautifulSoup(fetch(session,url),"html.parser")
        h=soup.find("h1")
        if not h:return None
        title=" ".join(h.stripped_strings)
        # Typical: Fußball live am 03.10.2026, Wettbewerb, Heim - Auswärts
        m=re.search(r"Fußball live am\s+\d{2}\.\d{2}\.\d{4},\s*(.*?),\s*(.+?)\s+-\s+(.+)$",title,re.I)
        if not m:return None
        text=" ".join(soup.stripped_strings)
        tm=re.search(r"\b([0-2]\d:[0-5]\d)\s*Uhr\b",text)
        if not tm:return None
        # Exclude entries without a listed transmission.
        section=text
        if "Alle Live-Übertragungen" in section:section=section.split("Alle Live-Übertragungen",1)[1]
        if "Diese Seite teilen" in section:section=section.split("Diese Seite teilen",1)[0]
        if re.sub(r"Keine Übertragungen|TV|HD-TV|Internet \(Livestream\)|\(Web-\)Radio|Smartphone / Tablet|Set-Top-Box / Stick / Konsole|Smart TV","",section).strip()=="":
            return None
        return {"date":date,"time":tm.group(1),"competition":m.group(1).strip(),"home":m.group(2).strip(),"away":m.group(3).strip(),"url":url}
    except Exception as e:
        return {"error":str(e),"url":url}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--report",default="source-coverage-report.md")
    args=ap.parse_args()
    date=args.date or dt.datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()
    day_url=f"{BASE}/fussball-heute?date={date}"
    session=requests.Session()

    try:
        soup=BeautifulSoup(fetch(session,day_url),"html.parser")
    except Exception as e:
        Path(args.report).write_text(f"# Quellenabgleich fehlgeschlagen\n\n{e}\n")
        print(e,file=sys.stderr);return 2

    urls=[]
    for a in soup.find_all("a",href=True):
        href=a["href"]
        if "/match/" in href:
            u=urljoin(BASE,href)
            if u not in urls:urls.append(u)

    source=[]
    failures=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs=[pool.submit(parse_match,session,u,date) for u in urls]
        for f in as_completed(futs):
            row=f.result()
            if not row:continue
            if "error" in row:failures.append(row)
            else:source.append(row)

    local=[g for g in json.loads((ROOT/"games.json").read_text()) if g.get("date")==date and g.get("channels")]
    missing=[];time_conflicts=[];matched_local=set()

    for src in source:
        ranked=sorted(((pair_score(src,g),i,g) for i,g in enumerate(local)),reverse=True,key=lambda x:x[0])
        score,i,g=ranked[0] if ranked else (0,None,None)
        if score<0.72:
            missing.append(src);continue
        matched_local.add(i)
        if src["time"]!=g["time"]:
            time_conflicts.append((src,g,score))

    report=[
      "# Externer Quellenabgleich",
      "",
      f"- Datum: **{date}**",
      f"- fussballgucken.info: **{len(source)}** Partien mit Match-/Übertragungsseite",
      f"- Spieltag Aktuell: **{len(local)}** veröffentlichte Partien",
      f"- Nicht sicher zugeordnet: **{len(missing)}**",
      f"- Abweichende Uhrzeiten: **{len(time_conflicts)}**",
      f"- Nicht lesbare Detailseiten: **{len(failures)}**",
      "",
      "Hinweis: Der Abgleich ist ein Warnsystem. Änderungen werden nicht blind aus einer Aggregator-Quelle importiert, sondern müssen bei Konflikten mit Liga, Verein oder Sender gegengeprüft werden.",
      ""
    ]
    if missing:
      report+=["## Möglicherweise fehlende Partien",""]
      report += [f"- {x['time']} · {x['home']} – {x['away']} · {x['competition']} · {x['url']}" for x in sorted(missing,key=lambda x:(x["time"],x["home"]))]
      report.append("")
    if time_conflicts:
      report+=["## Abweichende Uhrzeiten",""]
      for src,g,score in time_conflicts:
        report.append(f"- {src['home']} – {src['away']}: Quelle **{src['time']}**, lokal **{g['time']}** · {src['url']}")
      report.append("")
    Path(args.report).write_text("\n".join(report)+"\n")
    print("\n".join(report))

    # Differences are actionable, but parser failures alone should not mark data wrong.
    return 1 if missing or time_conflicts else 0

if __name__=="__main__":
    raise SystemExit(main())
