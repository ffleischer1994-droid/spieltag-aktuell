#!/usr/bin/env python3
"""Refresh the rolling broadcast window; abort without writing on source failure."""
import argparse
import datetime as dt
import json
import os
import hashlib
import time
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://fussballgucken.info'


def fetch(url):
    cache = Path(os.environ['SPIELTAG_SOURCE_CACHE']) / (hashlib.sha256(url.encode()).hexdigest()+'.html') if os.environ.get('SPIELTAG_SOURCE_CACHE') else None
    if cache and cache.exists(): return BeautifulSoup(cache.read_text(), 'html.parser')
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=30, headers={'User-Agent': 'SpieltagAktuell/1.0 (+https://spieltagaktuell.de/datenquellen/)'})
            response.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 2: raise
            time.sleep(2 ** attempt)
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(response.text)
    return BeautifulSoup(response.text, 'html.parser')


def channels_from(element):
    result = []
    for a in element.select('a[href^="/sender/"]'):
        label = a.get_text(' ', strip=True)
        li = a.find_parent('li')
        if li and li.select_one('.fg-icon-radio'): continue
        if re.search(r'Radio|Hörfunk|Audio|Haching FM|LOKruf|Bullenfunk|Knappen-Kommentar|WDR Event', label, re.I):
            continue
        label = re.sub(r' HD$', '', label)
        if label.startswith('Sky Go') or label == 'Sky Stream': continue
        if label.startswith('WOW'):
            label = 'WOW (AT)' if 'Austria' in label else 'WOW'
        if label.startswith('Sky (Schweiz)'): label = 'Sky (CH)'
        if label.startswith('Swisscom'): label = 'blue Sport (CH)'
        if label.startswith('DFB.TV') and not label.startswith('DFB.TV+'): label = 'DFB.TV'
        if label.lower().startswith(("l'équipe", "l’équipe")): label = "L'Équipe (FR)"
        if label.startswith('DAZN'): label = 'DAZN'
        elif label.startswith('MagentaSport'): label = 'MagentaSport'
        elif label.startswith('OneFootball'): label = 'OneFootball'
        elif label.startswith('Disney+'): label = 'Disney+'
        elif label.startswith('Apple TV'): label = 'Apple TV'
        elif label.startswith('FIFA+'): label = 'FIFA+'
        elif label.startswith('Sportdigital+'): label = 'Sportdigital+'
        elif label.startswith('blue Sport'): label = 'blue Sport (CH)'
        elif label.startswith('blue Zoom'): label = 'blue Zoom (CH)'
        elif label.startswith(('ORF', 'Sky Sport Austria')) or '(Austria)' in label:
            label = re.sub(r' \(.*$', '', label) + ' (AT)'
        elif label.startswith(('SRF', 'RTS', 'RSI')):
            label = re.sub(r' \(.*$', '', label) + ' (CH)'
        elif label.startswith('Sky Go'): continue
        elif re.search(r'\((?:App|Amazon|Android|Apple|Chromecast|Huawei|Smart|Sat|Set-Top|PlayStation|Xbox)', label): continue
        if label and label not in result: result.append(label)
    return result


def groups_for(channels):
    groups = []
    for c in channels:
        if 'DAZN' in c: group = 'dazn'
        elif re.search(r'Sky|WOW', c, re.I) and '(AT)' not in c and '(CH)' not in c: group = 'sky'
        elif 'Prime' in c: group = 'prime'
        # Only explicit German public/free services, never infer from OneFootball.
        elif re.match(r'^(?:ARD|Das Erste|ZDF|BR24|BR \(|WDR|NDR|MDR|SWR|RBB|rbb|hr |SPORT1$|FIFA\+)', c): group = 'free'
        else: group = 'other'
        if group not in groups: groups.append(group)
    return groups


def read_day(date):
    url = f'{BASE}/fussball-heute?date={date}'
    soup = fetch(url)
    heading = soup.select_one('#date-' + date.replace('-', ''))
    if not heading:
        raise ValueError(f'{date}: source returned no matching date section')
    def parse_item(item):
        home, away = item.select_one('.team-home'), item.select_one('.team-guest')
        if not home or not away: return None
        competition = item.select_one('.meta-competition').get_text(' ', strip=True)
        if re.search(r'Icon League', competition, re.I): return None
        time = item.select_one('.meta-time').get_text(strip=True)
        if not re.fullmatch(r'\d{2}:\d{2}', time): raise ValueError(f'{date}: invalid time')
        link = item.select_one('a[href^="/match/"]')
        match_url = urljoin(BASE, link['href'])
        detail = fetch(match_url)
        expected_date = dt.date.fromisoformat(date).strftime('%d.%m.%Y')
        if not detail.h1 or expected_date not in detail.h1.get_text(' ', strip=True):
            raise ValueError(f'{date}: wrong date on match detail: {match_url}')
        coverage = detail.select('.list-coverage')
        channels = list(dict.fromkeys(c for section in coverage for c in channels_from(section)))
        if not channels:
            print(f'{date}: skipping entry without confirmed video broadcast: {match_url}', flush=True)
            return None
        flag = item.select_one('.meta-flag a')
        country = flag.get('title', '').removeprefix('Länderseite ').strip() if flag else 'International'
        return dict(date=date, time=time, competition=competition, country=country or 'International',
                         home=home.get_text(' ', strip=True), away=away.get_text(' ', strip=True),
                         channels=channels, groups=groups_for(channels),
                         sources=[{'url':url,'name':f'fußballgucken.info – Tagesplan {date}'},
                                  {'url':match_url,'name':'Übertragungsdetails'}],
                         verifiedAt=dt.datetime.now(dt.timezone.utc).isoformat())
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = [g for g in pool.map(parse_item, soup.select('.item.game')) if g]
    if not rows: raise ValueError(f'{date}: empty source; retaining existing dataset')
    print(f'{date}: {len(rows)} games', flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--today')
    args = ap.parse_args()
    today = dt.date.fromisoformat(args.today) if args.today else dt.datetime.now(ZoneInfo('Europe/Berlin')).date()
    dates = [(today + dt.timedelta(days=i)).isoformat() for i in range(7)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = [g for day in pool.map(read_day, dates) for g in day]
    rows.sort(key=lambda g:(g['date'],g['time'],g['home'],g['away']))
    keys = [(g['date'],g['time'],g['home'],g['away']) for g in rows]
    if len(keys) != len(set(keys)): raise ValueError('Duplicate source fixtures')
    target = ROOT / 'games.json'
    # Keep researched supplemental evidence for otherwise identical fixtures.
    old = {(g['date'],g['home'],g['away']):g for g in json.loads(target.read_text())}
    for g in rows:
        previous = old.get((g['date'],g['home'],g['away']), {})
        if previous.get('time') == g['time']:
            g['sources'] += [s for s in previous.get('sources',[]) if s not in g['sources']]
            if previous.get('channelLinks'): g['channelLinks'] = previous['channelLinks']
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(target)

if __name__ == '__main__': main()
