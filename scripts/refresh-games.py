#!/usr/bin/env python3
"""Refresh the rolling broadcast window; abort without writing on source failure."""
import argparse
import datetime as dt
import json
import os
import hashlib
import time
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://fussballgucken.info'
AUDIO_RX = re.compile('|'.join(json.loads((ROOT/'scripts/broadcast-audio.json').read_text())), re.I)

DAZN_REGION_LABELS = {'DAZN (Austria)': 'DAZN (AT)', 'DAZN (Schweiz)': 'DAZN (CH)'}
DAZN_REGION_LINKS = {
    'DAZN (AT)': 'https://www.dazn.com/de-AT/home',
    'DAZN (CH)': 'https://www.dazn.com/de-CH/home',
}


# Official fixture confirmation takes precedence over a conflicting listing time.
VERIFIED_KICKOFFS = {
    'https://fussballgucken.info/match/194701/regionalliga-nordost/bfc-dynamo-hallescher-fc': (
        '2026-11-22', '18:00', 'https://www.hallescherfc.de/news/spielverlegung-auswaertsspiel-gegen-bfc-dynamo'),
    'https://fussballgucken.info/match/193937/champions-league-frauen/benfica-lissabon-frauen-fk-austria-wien-frauen': (
        '2026-11-12', '21:00',
        'https://www.uefa.com/news-media/news/02ab-2209e8267c40-cadb2ec0869e-1000--uefa-matches-in-portugal-postponed-due-to-storm-charles/'),
    'https://fussballgucken.info/match/198373/afrika-cup/aegypten-malawi': (
        '2026-11-13', '20:00',
        'https://www.cafonline.com/afcon2025/news/crucial-matchdays-3-and-4-to-shape-totalenergies-caf-afcon-pamoja-2027-qualification-race/'),
    'https://fussballgucken.info/match/198460/laenderspiel-herren/malta-eswatini': (
        '2026-11-12', '18:30',
        'https://www.mfa.com.mt/news/national-teams/malta-to-face-eswatini-in-international-friendly-ahead-of-final-unl-fixture/'),
    'https://fussballgucken.info/match/193634/premier-league-england/fc-fulham-newcastle-united': (
        '2026-11-07', '16:00',
        'https://www.premierleague.com/en/news/4725574'),
    'https://fussballgucken.info/match/193630/premier-league-england/fc-arsenal-hull-city-afc': (
        '2026-11-07', '16:00',
        'https://www.premierleague.com/en/news/4725574'),
    'https://fussballgucken.info/match/193925/champions-league-frauen/fc-barcelona-frauen-fc-arsenal-wfc-frauen': (
        '2026-11-12', '18:45',
        'https://www.fcbarcelona.com/en/football/womens-football/news/4592187/fc-barcelona-statement'),
    'https://fussballgucken.info/match/197457/premiere-ligue-frankreich/fc-nantes-frauen-fc-toulouse-frauen': (
        '2026-11-06', '19:00',
        'https://www.toulousefc.com/play/blog/2026/11/le-match-des-violettes-face-au-fc-nantes-est-avance-au-vendredi'),
    'https://fussballgucken.info/match/198168/fa-cup-england/plymouth-parkway-berkhamsted-fc': (
        '2026-11-09', '20:30',
        'https://www.ppfc.co.uk/fa-cup-ticket-information/'),
}


AFCON_QUALIFIER_SCHEDULE = 'https://www.cafonline.com/afcon2025/news/crucial-matchdays-3-and-4-to-shape-totalenergies-caf-afcon-pamoja-2027-qualification-race/'


# Official competition labels for listings that conflate qualifiers and finals.
VERIFIED_COMPETITIONS = {
    ('2026-11-15', 'https://fussballgucken.info/match/198580/national-women-s-soccer-league-nwsl/nj-ny-gotham-fc-frauen-kansas-city-current-frauen'): (
        'NWSL (Playoffs)', 'https://www.nwslsoccer.com/news/semifinal-round-set-for-2026-nwsl-playoffs-presented-by-google-pixel'),
    ('2026-11-14', 'https://fussballgucken.info/match/198579/national-women-s-soccer-league-nwsl/washington-spirit-frauen-utah-royals-fc-frauen'): (
        'NWSL (Playoffs)', 'https://www.nwslsoccer.com/news/semifinal-round-set-for-2026-nwsl-playoffs-presented-by-google-pixel'),
    ('2026-11-14', 'https://fussballgucken.info/match/198590/u17-em/deutschland-u17-litauen-u17'): (
        'U17-EM-Qualifikation', 'https://www.dfb.de/maenner/nationalmannschaften/u-17/spiele-und-termine'),
    ('2026-11-17', 'https://fussballgucken.info/match/198591/u17-em/nordirland-u17-deutschland-u17'): (
        'U17-EM-Qualifikation', 'https://www.dfb.de/maenner/nationalmannschaften/u-17/spiele-und-termine'),
    ('2026-11-12', 'https://fussballgucken.info/match/198570/u19-em/deutschland-u19-schweden-u19'): (
        'U19-EM-Qualifikation', 'https://www.dfb.de/maenner/nationalmannschaften/u-19/spiele-und-termine'),
    ('2026-11-14', 'https://fussballgucken.info/match/198569/u19-em/portugal-u19-deutschland-u19'): (
        'U19-EM-Qualifikation', 'https://www.dfb.de/maenner/nationalmannschaften/u-19/spiele-und-termine'),
    ('2026-11-17', 'https://fussballgucken.info/match/198571/u19-em/litauen-u19-deutschland-u19'): (
        'U19-EM-Qualifikation', 'https://www.dfb.de/maenner/nationalmannschaften/u-19/spiele-und-termine'),
    ('2026-11-11', 'https://fussballgucken.info/match/198457/u17-em/deutschland-u17-aserbaidschan-u17'): (
        'U17-EM-Qualifikation',
        'https://datencenter.dfb.de/datencenter/em-qualifikation-1242/2026-27/gruppe-2/deutschland-u-17-m-aserbaidschan-u-17-2413487'),
}


# Researched video coverage missing from the listing; date-scoped and sourced.
VERIFIED_BROADCASTS = {
    ('2026-11-12', 'https://fussballgucken.info/match/198530/freundschaftsspiel/1-fc-moenchengladbach-standard-luettich'): {
        'home': 'Borussia Mönchengladbach',
        'channels': ['FohlenTV'],
        'url': 'https://www.borussia.de/de/tickets',
        'name': 'Borussia: Testspiel am 12. November um 14:00 Uhr auf FohlenTV',
        'channelLinks': {'FohlenTV': 'https://tv.borussia.de/app.php/'},
        'freeChannels': {'FohlenTV'},
        'additionalSources': [{'url': 'https://www.90min.de/borussia-monchengladbach-gegen-standard-luttich-testspiel-live-im-kostenlosen-stream-12-11-2026',
                               'name': 'FohlenTV: kostenlos nach Login'}],
    },
    ('2026-11-14', 'https://fussballgucken.info/match/197589/2-frauen-bundesliga/vfl-bochum-frauen-1899-hoffenheim-ii-frauen'): {
        'channels': ['DFB.TV'],
        'url': 'https://www.dfb.de/news/klopp-pk-und-u-teams-live-das-laeuft-diese-woche-auf-dfbtv',
        'name': 'DFB: bestätigte Liveübertragung auf DFB.TV',
        'channelLinks': {'DFB.TV': 'https://watch.dfbtvplus.de/'},
    },
    ('2026-11-15', 'https://fussballgucken.info/match/196207/frauen-regionalliga-west/borussia-dortmund-frauen-fc-schalke-04-frauen'): {
        'channels': ['DFB.TV', 'Staige'],
        'url': 'https://www.bvb.de/de/de/aktuelles/news/news.html/Alle-BVB-Uebertragungen-auf-einen-Blick.html',
        'name': 'BVB: Pluto TV und Staige; DFB bestätigt zusätzlich DFB.TV',
        'channelLinks': {'DFB.TV': 'https://watch.dfbtvplus.de/', 'Staige': 'https://staige.tv/spiel/566137', 'Pluto TV': 'https://pluto.tv/gsa/live-tv/66337ea1307fa300082c28a0'},
        'additionalSources': [{'url': 'https://www.dfb.de/news/klopp-pk-und-u-teams-live-das-laeuft-diese-woche-auf-dfbtv', 'name': 'DFB: bestätigte Liveübertragung auf DFB.TV'}],
    },
    ('2026-11-14', 'https://fussballgucken.info/match/197292/landespokal-sachsen/bsg-stahl-riesa-fsv-zwickau'): {
        'channels': ['LVZ+', 'Sächsische Zeitung', 'Torgauer Zeitung'],
        'url': 'https://www.lvz.de/sport/regional/regionalliga-nordost-und-sachsenpokal-live-diese-partien-uebertragen-wir-UIZKBOXN4JGLFN7JUL5Z4Y7AUY.html',
        'name': 'Offizieller Sachsenpokal-Sendeplan von LVZ und Sächsischer Zeitung',
        'channelLinks': {'LVZ+': 'https://www.lvz.de/livesport', 'Sächsische Zeitung': 'https://www.saechsische.de/livesport', 'Torgauer Zeitung': 'https://www.torgauerzeitung.de/livesport'},
    },
    ('2026-11-15', 'https://fussballgucken.info/match/197294/landespokal-sachsen/fc-eilenburg-chemnitzer-fc'): {
        'channels': ['LVZ+', 'Sächsische Zeitung', 'Torgauer Zeitung'],
        'url': 'https://www.lvz.de/sport/regional/regionalliga-nordost-und-sachsenpokal-live-diese-partien-uebertragen-wir-UIZKBOXN4JGLFN7JUL5Z4Y7AUY.html',
        'name': 'Offizieller Sachsenpokal-Sendeplan von LVZ und Sächsischer Zeitung',
        'channelLinks': {'LVZ+': 'https://www.lvz.de/livesport', 'Sächsische Zeitung': 'https://www.saechsische.de/livesport', 'Torgauer Zeitung': 'https://www.torgauerzeitung.de/livesport'},
    },
    ('2026-11-10', 'https://fussballgucken.info/match/193913/champions-league-frauen/paris-st-germain-frauen-fc-bayern-muenchen-frauen'): {
        'channels': ['ZDF-Streaming'],
        'url': 'https://www.zdf.de/video/kurzfassungen/uefa-champions-league-der-frauen-highlights-100/paris-saint-germain-fc-bayern-livestream-spieltag-4-100',
        'name': 'ZDF – kostenloser Livestream',
    },
    ('2026-11-12', 'https://fussballgucken.info/match/194697/nations-league/italien-frankreich'): {
        'channels': ['DAZN'],
        'url': 'https://couchultras.com/fussball/laenderspiele/italien-frankreich-85221',
        'name': 'Italien – Frankreich: DAZN am 12. November um 20:45 Uhr',
    },
    ('2026-11-11', 'https://fussballgucken.info/match/197213/uefa-women-s-europa-cup/eintracht-frankfurt-frauen-psv-eindhoven-frauen'): {
        'channels': ['EintrachtTV+'],
        'url': 'https://frauen.eintracht.de/uefa-women-s-europa-cup/spielplan/eintracht-frankfurt-ladies-psv-women/vorschau/',
        'name': 'Eintracht Frankfurt: Rückspiel am 11. November live auf EintrachtTV+',
    },
    ('2026-11-10', 'https://fussballgucken.info/match/197214/uefa-women-s-europa-cup/feyenoord-rotterdam-frauen-vfl-wolfsburg-frauen'): {
        'channels': ['Feyenoord ONE (NL)', 'Wölfe TV'],
        'url': 'https://one.feyenoord.nl/schedule?uid=16985837558',
        'name': 'Feyenoord ONE – bestätigter Livestream (Niederlande)',
        'additionalSources': [{'url': 'https://www.vfl-wolfsburg.de/newsdetails/news-detail/detail/news/vfl-frauen-wollen-welle-weiterreiten', 'name': 'VfL Wolfsburg: kostenloser Wölfe-TV-Livestream des Rückspiels'}],
        'channelLinks': {'Feyenoord ONE (NL)': 'https://one.feyenoord.nl/schedule?uid=16985837558',
                         'Wölfe TV': 'https://www.vfl-wolfsburg.de/newsdetails/news-detail/detail/news/vfl-frauen-wollen-welle-weiterreiten'},
        'freeChannels': {'Wölfe TV'},
    },
}


# Match-specific listings contradicted by official broadcaster information.
EXCLUDED_BROADCASTS = {
    ('2026-11-07', 'https://fussballgucken.info/match/193630/premier-league-england/fc-arsenal-hull-city-afc'): {'Sky Sport 8', 'Sky Sport 08'},
    # The club confirms EintrachtTV+, without a separate free broadcast.
    ('2026-11-11', 'https://fussballgucken.info/match/197213/uefa-women-s-europa-cup/eintracht-frankfurt-frauen-psv-eindhoven-frauen'): {'EintrachtTV (Frankfurt)'},
}


# Confirmed fixtures not yet present in the daily listing.
VERIFIED_ADDITIONAL_FIXTURES = [{
    'date': '2026-11-20', 'time': '19:00',
    'competition': 'Regionalliga Nordost', 'country': 'Deutschland',
    'home': '1. FC Magdeburg II', 'away': 'FSV Zwickau',
    'channels': ['MDR (Livestream)'],
    'sources': [
        {'url': 'https://www.mdr.de/sport/live/livestreams/sport-livestreams-mdr-100.html', 'name': 'MDR: bestätigter Livestream'},
    ],
    'channelLinks': {'MDR (Livestream)': 'https://www.mdr.de/sport/live/livestreams/sport-livestreams-mdr-100.html'},
}, {
    'date': '2026-11-14', 'time': '18:00',
    'competition': 'NWSL (Playoffs)', 'country': 'USA',
    'home': 'Washington Spirit ♀', 'away': 'Utah Royals FC ♀',
    'channels': ['Sportdigital1+', 'Sportdigital+'],
    'sources': [
        {'url': 'https://www.nwslsoccer.com/news/semifinal-round-set-for-2026-nwsl-playoffs-presented-by-google-pixel', 'name': 'NWSL: offizieller Halbfinalspielplan'},
        {'url': 'https://start.sportdigital.de/ankuendigung/77/chelsea-gegen-man-city', 'name': 'Sportdigital: bestätigte Liveübertragung'},
        {'url': 'https://start.sportdigital.de/mediathek/36882/Washington%2BSpirit%2B-%2BUtah%2BRoyals%2BFC', 'name': 'Sportdigital+: offizieller Livestream'},
    ],
    'channelLinks': {'Sportdigital+': 'https://start.sportdigital.de/mediathek/36882/Washington%2BSpirit%2B-%2BUtah%2BRoyals%2BFC'},
}, {
    'date': '2026-11-15', 'time': '21:00',
    'competition': 'NWSL (Playoffs)', 'country': 'USA',
    'home': 'NJ/NY Gotham FC ♀', 'away': 'Kansas City Current ♀',
    'channels': ['Sportdigital1+', 'Sportdigital+'],
    'sources': [
        {'url': 'https://www.nwslsoccer.com/news/semifinal-round-set-for-2026-nwsl-playoffs-presented-by-google-pixel', 'name': 'NWSL: offizieller Halbfinalspielplan'},
        {'url': 'https://start.sportdigital.de/ankuendigung/77/chelsea-gegen-man-city', 'name': 'Sportdigital: bestätigte Liveübertragung'},
        {'url': 'https://start.sportdigital.de/mediathek/36890/Gotham%2BFC%2B-%2BKansas%2BCity%2BCurrent', 'name': 'Sportdigital+: offizieller Livestream'},
    ],
    'channelLinks': {'Sportdigital+': 'https://start.sportdigital.de/mediathek/36890/Gotham%2BFC%2B-%2BKansas%2BCity%2BCurrent'},
}, {
    'date': '2026-11-12', 'time': '14:00',
    'competition': 'Testspiel (Vereine)', 'country': 'Deutschland',
    'home': 'FC Energie Cottbus', 'away': 'FC Erzgebirge Aue',
    'channels': ['FCEnergieTV (YouTube)'],
    'sources': [
        {'url': 'https://www.fcenergie.de/testspiele.html', 'name': 'FC Energie Cottbus: offizieller Spieltermin'},
        {'url': 'https://www.niederlausitz-aktuell.de/niederlausitz-aktuell/orte/cottbus/331923/testspiel-in-der-laenderspielpause-energie-cottbus-trifft-auf-aue.html',
         'name': 'Niederlausitz aktuell: bestätigter Vereinslivestream'},
    ],
    'channelLinks': {'FCEnergieTV (YouTube)': 'https://www.youtube.com/@fcenergietv'},
}, {
    'date': '2026-11-15', 'time': '15:00',
    'competition': 'Testspiel (Vereine)', 'country': 'Deutschland',
    'home': 'Hamburger SV', 'away': 'HNK Hajduk Split',
    'channels': ['Sky Sport News', 'Sky Sport Bundesliga', 'Sky Sport (Livestream)'],
    'sources': [
        {'url': 'https://www.hsv.de/news/44-444-tickets-fuer-die-44-vorfreude-auf-hajduk-test',
         'name': 'Hamburger SV: offizieller Spieltermin'},
        {'url': 'https://sport.sky.de/fussball/artikel/bundesliga-testspiele-live-auf-sky-sport/12129058/34089',
         'name': 'Sky Sport: TV- und Streamübertragung ab 14:55 Uhr'},
    ],
    'channelLinks': {
        'Sky Sport (Livestream)': 'https://sport.sky.de/fussball/artikel/bundesliga-testspiele-live-auf-sky-sport/12129058/34089',
    },
}, {
    'date': '2026-11-12', 'time': '14:00',
    'competition': 'Testspiel (Vereine)', 'country': 'Deutschland',
    'home': 'SpVgg Greuther Fürth', 'away': 'Würzburger Kickers',
    'channels': ['Greuther Fürth (YouTube)'],
    'sources': [
        {'url': 'https://www.sgf1903.de/news/profis/testspiel-gegen-wuerzburg',
         'name': 'Greuther Fürth: Anstoß und YouTube-Livestream ab 14 Uhr'},
    ],
    'channelLinks': {'Greuther Fürth (YouTube)': 'https://www.youtube.com/@DasKleeblattFuerth'},
}, {
    'date': '2026-11-16', 'time': '14:00',
    'competition': 'Afrika-Cup-Qualifikation', 'country': 'International',
    'home': 'Sudan', 'away': 'Senegal',
    'channels': ['DAZN 2'],
    'sources': [
        {'url': AFCON_QUALIFIER_SCHEDULE, 'name': 'CAF – offizieller Spielplan der Qualifikation'},
        {'url': 'https://www.prisma.de/tv-programm/Africa-Cup-of-Nations-Qualifikation-2027,58288200', 'name': 'DAZN 2: TV-Programm für Sudan gegen Senegal'},
    ],
}, {
    'date': '2026-11-16', 'time': '16:00',
    'competition': 'Afrika-Cup-Qualifikation', 'country': 'International',
    'home': 'Somalia', 'away': 'Ghana',
    'channels': ['DAZN 2'],
    'sources': [
        {'url': AFCON_QUALIFIER_SCHEDULE, 'name': 'CAF – offizieller Spielplan der Qualifikation'},
        {'url': 'https://www.prisma.de/tv-programm/Africa-Cup-of-Nations-Qualifikation-2027,58288202', 'name': 'DAZN 2: TV-Programm für Somalia gegen Ghana'},
    ],
}, {
    'date': '2026-11-11', 'time': '17:00',
    'competition': "UEFA Women's Europa Cup", 'country': 'International',
    'home': 'Czarni Sosnowiec ♀', 'away': 'SK Brann ♀',
    'channels': ['VG+ Sport (NO)', 'BT.no (NO)'],
    'sources': [
        {'url': 'https://www.brann.no/nyheter/her-er-troppen-som-reiser-til-polen%202026',
         'name': 'SK Brann: Anstoß und Übertragungen auf VG+ und BT.no'},
        {'url': 'https://vglive.vg.no/fotball/event/czarni-sosnowiec-brann/775334',
         'name': 'VG+ Sport: Übertragungsseite'},
    ],
    'channelLinks': {'VG+ Sport (NO)': 'https://vglive.vg.no/fotball/event/czarni-sosnowiec-brann/775334'},
}, {
    'date': '2026-11-11', 'time': '18:00',
    'competition': "UEFA Women's Europa Cup", 'country': 'International',
    'home': 'Brøndby IF ♀', 'away': 'Rosenborg BK ♀',
    'channels': ['VG+ Sport (NO)'],
    'sources': [
        {'url': 'https://www.rbk.no/lag/a-lag-kvinner/import/tournament/uefa-womens-europa-cup-2026/season/fotballsesongen-2026/match/europa-cup-brondby-rosenborg',
         'name': 'Rosenborg: offizieller Anstoß um 18:00 Uhr'},
        {'url': 'https://vglive.vg.no/fotball/event/br%C3%B8ndby-if-rosenborg/775330',
         'name': 'VG+ Sport: Übertragungsseite'},
    ],
    'channelLinks': {'VG+ Sport (NO)': 'https://vglive.vg.no/fotball/event/br%C3%B8ndby-if-rosenborg/775330'},
}, {
    'date': '2026-11-11', 'time': '18:00',
    'competition': "UEFA Women's Europa Cup", 'country': 'International',
    'home': 'Fenerbahçe Istanbul ♀', 'away': 'Real Sociedad ♀',
    'channels': ['TRT Spor (TR)'],
    'sources': [
        {'url': 'https://www.realsociedad.eus/es/noticias/detalle/dos-grandes-citas-por-delante',
         'name': 'Real Sociedad: offizieller Anstoß um 18:00 Uhr MEZ'},
        {'url': 'https://www.sporekrani.com/home/match/497066/2026/11/11/fenerbahce-arsavev-real-sociedad-uefa-kadinlar-avrupa-sampiyonasi-hangi-kanalda',
         'name': 'Spor Ekranı: Übertragung auf TRT Spor'},
        {'url': 'https://www.aspor.com.tr/',
         'name': 'A Spor: TV-Spielplan nennt TRT Spor'},
    ],
}, {
    'date': '2026-11-11', 'time': '19:00',
    'competition': "UEFA Women's Europa Cup", 'country': 'International',
    'home': 'Hammarby IF ♀', 'away': 'Spartak Myjava ♀',
    'channels': ['Sportbladet Play (SE)', 'STVR Šport (SK)'],
    'sources': [
        {'url': 'https://hammarby-if.se/nu-kokar-det-i-bajenland/',
         'name': 'Hammarby: Anstoß um 19:00 Uhr und Sportbladet-Livestream'},
        {'url': 'https://www.stvr.sk/program?date=2026-11-11',
         'name': 'STVR Šport: offizieller Sendeplan'},
    ],
    'channelLinks': {'Sportbladet Play (SE)': 'https://tv.aftonbladet.se/video/408413/europa-cup-hammarby-spartak-myjava',
                     'STVR Šport (SK)': 'https://www.stvr.sk/program?date=2026-11-11'},
}, {
    'date': '2026-11-11', 'time': '19:00',
    'competition': "UEFA Women's Europa Cup", 'country': 'International',
    'home': 'Malmö FF ♀', 'away': 'Ajax Amsterdam ♀',
    'channels': ['MFF Play (SE)'],
    'sources': [
        {'url': 'https://www.mff.se/nyheter/se-malmo-ff-ajax-fc-pa-mff-play-2026-11-09/',
         'name': 'Malmö FF: Anstoß um 19:00 Uhr und MFF-Play-Livestream'},
    ],
    'channelLinks': {'MFF Play (SE)': 'https://mffplay.se/mffplay/watch/malmoe-ff-afc-ajax'},
}, {
    'date': '2026-11-12', 'time': '18:00',
    'competition': "UEFA Women's Europa Cup", 'country': 'International',
    'home': 'SCU Torreense ♀', 'away': 'Sparta Prag ♀',
    'channels': ['ČT sport Plus (CZ)'],
    'sources': [{'url': 'https://www.uefa.com/news-media/news/02ab-2209e8267c40-cadb2ec0869e-1000--uefa-matches-in-portugal-postponed-due-to-storm-charles/',
                 'name': 'UEFA: wegen Sturm Charles auf Donnerstag um 18:00 Uhr MEZ verlegt'},
                {'url': 'https://fortunaligazen.cz/clanek/304-sparta-zabojuje-v-portugalsku-o-postup-do-ctvrtfinale-europa-cupu',
                 'name': 'Fortuna liga: ČT sport Plus überträgt den Ersatztermin live'}],
    'channelLinks': {'ČT sport Plus (CZ)': 'https://sport.ceskatelevize.cz/'},
}, {
    'date': '2026-11-11', 'time': '17:00',
    'competition': 'Première Ligue (Frankreich)', 'country': 'Frankreich',
    'home': 'FC Fleury 91 ♀', 'away': 'FC Toulouse ♀',
    'channels': ['Arkema Première Ligue (YouTube)'],
    'sources': [
        {'url': 'https://www.toulousefc.com/equipes/feminines/resultats-calendrier',
         'name': 'Offizieller Toulouse-Spielplan: Fleury am 11. November 17:00 Uhr'},
        {'url': 'https://www.foottv.fr/equipes/toulouse-feminines',
         'name': 'Bestätigte YouTube-Übertragung am 11. November'},
        {'url': 'https://www.mon-match.com/matchs/fleury-91-f-vs-toulouse-f-24-10-2026',
         'name': 'Weitere Bestätigung der YouTube-Übertragung und neuen Anstoßzeit'},
    ],
}, {
    'date': '2026-11-12', 'time': '11:00',
    'competition': 'Testspiel (Vereine)', 'country': 'Deutschland',
    'home': 'RB Leipzig', 'away': 'FK Mladá Boleslav',
    'channels': ['RB Leipzig (Vereinsstream)'],
    'sources': [
        {'url': 'https://rbleipzig.com/en/news/rb-leipzig-friendly-fk-mlada-boleslav-12-november-2026', 'name': 'RB Leipzig: Anstoß um 11 Uhr und bestätigter Vereinslivestream'},
        {'url': 'https://fkmb.cz/match/1215', 'name': 'FK Mladá Boleslav: offizieller Spieltermin'},
    ],
    'channelLinks': {'RB Leipzig (Vereinsstream)': 'https://rbleipzig.com/en/news/rb-leipzig-friendly-fk-mlada-boleslav-12-november-2026'},
}, {
    'date': '2026-11-12', 'time': '14:00',
    'competition': 'U19-EM-Qualifikation', 'country': 'International',
    'home': 'Deutschland (U19)', 'away': 'Schweden (U19)',
    'channels': ['DFB.TV'],
    'sources': [
        {'url': 'https://www.dfb.de/news/klopp-pk-und-u-teams-live-das-laeuft-diese-woche-auf-dfbtv', 'name': 'DFB: bestätigte Liveübertragung auf DFB.TV'},
        {'url': 'https://datencenter.dfb.de/datencenter/em-qualifikation-1231/2026-2027/2-runde-gruppe-3/deutschland-u-19-m-schweden-u-19-2418434', 'name': 'DFB-Datencenter: Anstoß 14:00 Uhr'},
    ],
    'channelLinks': {'DFB.TV': 'https://watch.dfbtvplus.de/'},
}, {
    'date': '2026-11-13', 'time': '12:30',
    'competition': 'Testspiel (Vereine)', 'country': 'Deutschland',
    'home': 'VfL Bochum', 'away': 'SC Verl',
    'channels': ['VfL Bochum (Vereinsstream)'],
    'sources': [
        {'url': 'https://www.vfl-bochum.de/aktuelles/2026/11/test-gegen-verl-unter-ausschluss-der-oeffentlichkeit/', 'name': 'VfL Bochum: Vereinslivestream angekündigt, YouTube voraussichtlich'},
    ],
    'channelLinks': {'VfL Bochum (Vereinsstream)': 'https://www.vfl-bochum.de/aktuelles/2026/11/test-gegen-verl-unter-ausschluss-der-oeffentlichkeit/'},
}, {
    'date': '2026-11-13', 'time': '13:00',
    'competition': 'Testspiel (Vereine)', 'country': 'Deutschland',
    'home': 'Dynamo Dresden', 'away': 'FK Dukla Prag',
    'channels': ['DynamoTV (YouTube)'],
    'sources': [
        {'url': 'https://www.dynamo-dresden.de/aktuelles/news/profis/testspiel-gegen-dukla-prag-angesetzt/', 'name': 'Dynamo Dresden: bestätigter Livestream auf dem Vereinskanal'},
    ],
    'channelLinks': {'DynamoTV (YouTube)': 'https://www.youtube.com/channel/UCTRY6TKbFpRuPvAIDJVKuaA'},
}, {
    'date': '2026-11-14', 'time': '11:00',
    'competition': 'U17-EM-Qualifikation', 'country': 'International',
    'home': 'Deutschland (U17)', 'away': 'Litauen (U17)',
    'channels': ['DFB.TV', 'DAZN'],
    'sources': [
        {'url': 'https://www.dfb.de/news/klopp-pk-und-u-teams-live-das-laeuft-diese-woche-auf-dfbtv', 'name': 'DFB: bestätigte Liveübertragung auf DFB.TV'},
        {'url': 'https://www.dfb.de/maenner/nationalmannschaften/u-17/spiele-und-termine', 'name': 'DFB: Anstoß um 11:00 Uhr'},
        {'url': 'https://www.livesoccertv.com/de/teams/germany/germany-u17/', 'name': 'TV-Programm: DAZN Deutschland, Österreich und Schweiz'},
    ],
    'channelLinks': {'DFB.TV': 'https://watch.dfbtvplus.de/'},
}, {
    'date': '2026-11-17', 'time': '11:00',
    'competition': 'U17-EM-Qualifikation', 'country': 'International',
    'home': 'Nordirland (U17)', 'away': 'Deutschland (U17)',
    'channels': ['DFB.TV', 'DFB.TV+', 'DAZN'],
    'sources': [
        {'url': 'https://www.dfb.de/news/klopp-pk-und-u-teams-live-das-laeuft-diese-woche-auf-dfbtv', 'name': 'DFB: bestätigte Liveübertragung und Empfang über DFB.TV+'},
        {'url': 'https://www.dfb.de/maenner/nationalmannschaften/u-17/spiele-und-termine', 'name': 'DFB: EM-Qualifikation, Anstoß um 11:00 Uhr'},
        {'url': 'https://www.livesoccertv.com/de/teams/germany/germany-u17/', 'name': 'TV-Programm: DAZN Deutschland, Österreich und Schweiz'},
    ],
    'channelLinks': {'DFB.TV': 'https://watch.dfbtvplus.de/', 'DFB.TV+': 'https://watch.dfbtvplus.de/'},
}, {
    'date': '2026-11-14', 'time': '18:00',
    'competition': 'U19-EM-Qualifikation', 'country': 'International',
    'home': 'Portugal (U19)', 'away': 'Deutschland (U19)',
    'channels': ['DFB.TV'],
    'sources': [
        {'url': 'https://www.dfb.de/news/klopp-pk-und-u-teams-live-das-laeuft-diese-woche-auf-dfbtv', 'name': 'DFB: bestätigte Liveübertragung auf DFB.TV'},
        {'url': 'https://datencenter.dfb.de/competitions/em-qualifikation-1231/seasons/2026-2027/teams/deutschland-u-19-m', 'name': 'DFB-Datencenter: Anstoß 18:00 Uhr'},
    ],
    'channelLinks': {'DFB.TV': 'https://watch.dfbtvplus.de/'},
}, {
    'date': '2026-11-17', 'time': '16:00',
    'competition': 'U19-EM-Qualifikation', 'country': 'International',
    'home': 'Litauen (U19)', 'away': 'Deutschland (U19)',
    'channels': ['DFB.TV', 'DFB.TV+'],
    'sources': [
        {'url': 'https://www.dfb.de/news/klopp-pk-und-u-teams-live-das-laeuft-diese-woche-auf-dfbtv', 'name': 'DFB: bestätigte Liveübertragung und Empfang über DFB.TV+'},
        {'url': 'https://www.dfb.de/maenner/nationalmannschaften/u-19/spiele-und-termine', 'name': 'DFB: EM-Qualifikation, Anstoß um 16:00 Uhr'},
    ],
    'channelLinks': {'DFB.TV': 'https://watch.dfbtvplus.de/', 'DFB.TV+': 'https://watch.dfbtvplus.de/'},
}, {
    'date': '2026-11-11', 'time': '14:00',
    'competition': 'Länderspiel (U16)', 'country': 'International',
    'home': 'Tschechien (U16)', 'away': 'Österreich (U16)',
    'channels': ['ÖFB TV (AT)'],
    'sources': [
        {'url': 'https://www.oefb.tv/de/live', 'name': 'ÖFB TV: offizieller Livestream-Spielplan'},
        {'url': 'https://www.oefb.at/oefb/News/MU16-CZEAUT-11112026-Kader', 'name': 'Offizieller Spielplan'},
    ],
    'channelLinks': {'ÖFB TV (AT)': 'https://www.oefb.tv/de/live'},
}, {
    'date': '2026-11-11', 'time': '18:00',
    'competition': 'U19-EM-Qualifikation', 'country': 'International',
    'home': 'Österreich (U19)', 'away': 'Belarus (U19)',
    'channels': ['ÖFB TV (AT)'],
    'sources': [
        {'url': 'https://www.oefb.tv/de/live', 'name': 'ÖFB TV: offizieller Livestream-Spielplan'},
        {'url': 'https://www.oefb.at/oefb/News/MU19-AUTBLR-11112026-Kader', 'name': 'Offizieller Spielplan'},
    ],
    'channelLinks': {'ÖFB TV (AT)': 'https://www.oefb.tv/de/live'},
}, {
    'date': '2026-11-13', 'time': '18:00',
    'competition': 'Frauen-Bundesliga (Österreich)', 'country': 'Österreich',
    'home': 'SK Sturm Graz ♀', 'away': 'First Vienna FC 1894 ♀',
    'channels': ['ORF SPORT+ (AT)'],
    'sources': [
        {'url': 'https://www.oefb.at/oefb/News/AFBL-26-27-Runde-13-Vorschau', 'name': 'ÖFB: offizielle Spieltagsvorschau und Liveübertragung'},
        {'url': 'https://tv.orf.at/program/orfs/livefussba1788.html', 'name': 'ORF SPORT+: bestätigte Liveübertragung'},
        {'url': 'https://sksturm.at/t/frauen/spielplan', 'name': 'Offizieller Spielplan'},
    ],
    'channelLinks': {'ORF SPORT+ (AT)': 'https://tv.orf.at/program/orfs/livefussba1788.html'},
}, {
    'date': '2026-11-14', 'time': '12:00',
    'competition': 'Länderspiel (U16)', 'country': 'International',
    'home': 'Österreich (U16)', 'away': 'Tschechien (U16)',
    'channels': ['ÖFB TV (AT)'],
    'sources': [
        {'url': 'https://www.oefb.tv/de/live', 'name': 'ÖFB TV: offizieller Livestream-Spielplan'},
        {'url': 'https://www.oefb.at/oefb/News/MU16-CZEAUT-11112026-Kader', 'name': 'Offizieller Spielplan'},
    ],
    'channelLinks': {'ÖFB TV (AT)': 'https://www.oefb.tv/de/live'},
}, {
    'date': '2026-11-14', 'time': '14:00',
    'competition': 'Frauen-Bundesliga (Österreich)', 'country': 'Österreich',
    'home': 'FC Blau-Weiß Linz/Kleinmünchen ♀', 'away': 'SpG Südburgenland / TSV Hartberg ♀',
    'channels': ['ÖFB TV (AT)', 'LAOLA1 (Livestream)'],
    'sources': [
        {'url': 'https://www.oefb.at/oefb/News/AFBL-26-27-Runde-13-Vorschau', 'name': 'ÖFB: offizielle Spieltagsvorschau und Liveübertragung'},
        {'url': 'https://www.oefb.tv/de/live', 'name': 'ÖFB TV: offizieller Livestream-Spielplan'},
        {'url': 'https://www.oefb.at/oefb/News/AFBL-Spielplan-2026-27-News', 'name': 'Offizieller Spielplan'},
    ],
    'channelLinks': {'ÖFB TV (AT)': 'https://www.oefb.tv/de/live'},
}, {
    'date': '2026-11-14', 'time': '14:00',
    'competition': 'Frauen-Bundesliga (Österreich)', 'country': 'Österreich',
    'home': 'SKN St. Pölten ♀', 'away': 'LASK ♀',
    'channels': ['ÖFB TV (AT)', 'LAOLA1 (Livestream)'],
    'sources': [
        {'url': 'https://www.oefb.at/oefb/News/AFBL-26-27-Runde-13-Vorschau', 'name': 'ÖFB: offizielle Spieltagsvorschau und Liveübertragung'},
        {'url': 'https://www.oefb.tv/de/live', 'name': 'ÖFB TV: offizieller Livestream-Spielplan'},
        {'url': 'https://www.oefb.at/oefb/News/AFBL-Spielplan-2026-27-News', 'name': 'Offizieller Spielplan'},
    ],
    'channelLinks': {'ÖFB TV (AT)': 'https://www.oefb.tv/de/live'},
}, {
    'date': '2026-11-14', 'time': '18:00',
    'competition': 'U19-EM-Qualifikation', 'country': 'International',
    'home': 'Österreich (U19)', 'away': 'Slowenien (U19)',
    'channels': ['ÖFB TV (AT)'],
    'sources': [
        {'url': 'https://www.oefb.tv/de/live', 'name': 'ÖFB TV: offizieller Livestream-Spielplan'},
        {'url': 'https://www.oefb.at/oefb/News/MU19-AUTBLR-11112026-Kader', 'name': 'Offizieller Spielplan'},
    ],
    'channelLinks': {'ÖFB TV (AT)': 'https://www.oefb.tv/de/live'},
}, {
    'date': '2026-11-15', 'time': '11:00',
    'competition': 'Frauen-Bundesliga (Österreich)', 'country': 'Österreich',
    'home': 'SCR Altach ♀', 'away': 'SK Rapid ♀',
    'channels': ['ÖFB TV (AT)', 'LAOLA1 (Livestream)'],
    'sources': [
        {'url': 'https://www.oefb.at/oefb/News/AFBL-26-27-Runde-13-Vorschau', 'name': 'ÖFB: offizielle Spieltagsvorschau und Liveübertragung'},
        {'url': 'https://www.oefb.tv/de/live', 'name': 'ÖFB TV: offizieller Livestream-Spielplan'},
        {'url': 'https://www.oefb.at/oefb/News/AFBL-Spielplan-2026-27-News', 'name': 'Offizieller Spielplan'},
    ],
    'channelLinks': {'ÖFB TV (AT)': 'https://www.oefb.tv/de/live'},
}, {
    'date': '2026-11-15', 'time': '15:00',
    'competition': '2. Frauen-Bundesliga (Österreich)', 'country': 'Österreich',
    'home': 'FC Wacker Innsbruck ♀', 'away': 'SPG SV Zaunergroup Wallern/Krenglbach ♀',
    'channels': ['ÖFB TV (AT)'],
    'sources': [
        {'url': 'https://www.oefb.tv/de/live', 'name': 'ÖFB TV: offizieller Livestream-Spielplan'},
        {'url': 'https://www.oefb.at/oefb/Bewerbe/Frauen/2-Frauen-Bundesliga', 'name': 'Offizieller Spielplan'},
    ],
    'channelLinks': {'ÖFB TV (AT)': 'https://www.oefb.tv/de/live'},
}, {
    'date': '2026-11-09', 'time': '18:15',
    'competition': 'Baller League UK', 'country': 'England',
    'home': 'Toma FC', 'away': 'N5 FC',
    'channels': ['Baller League UK (YouTube)'],
    'sources': [
        {'url': 'https://ballerleague.uk/en/game/238', 'name': 'Baller League UK: offizielle Ansetzung (in Berliner Zeit umgerechnet)'},
        {'url': 'https://ballerleague.uk/en', 'name': 'Baller League UK: YouTube-Livestream des 5. Spieltags'},
    ],
    'channelLinks': {'Baller League UK (YouTube)': 'https://www.youtube.com/watch?v=ksD12WtlRv0'},
}, {
    'date': '2026-11-09', 'time': '19:05',
    'competition': 'Baller League UK', 'country': 'England',
    'home': 'Prime FC', 'away': 'P17 FC',
    'channels': ['Baller League UK (YouTube)'],
    'sources': [
        {'url': 'https://ballerleague.uk/en/game/239', 'name': 'Baller League UK: offizielle Ansetzung (in Berliner Zeit umgerechnet)'},
        {'url': 'https://ballerleague.uk/en', 'name': 'Baller League UK: YouTube-Livestream des 5. Spieltags'},
    ],
    'channelLinks': {'Baller League UK (YouTube)': 'https://www.youtube.com/watch?v=ksD12WtlRv0'},
}, {
    'date': '2026-11-09', 'time': '20:00',
    'competition': 'Baller League UK', 'country': 'England',
    'home': 'Clutch FC', 'away': 'Gold Devils',
    'channels': ['Baller League UK (YouTube)'],
    'sources': [
        {'url': 'https://ballerleague.uk/en/game/240', 'name': 'Baller League UK: offizielle Ansetzung (in Berliner Zeit umgerechnet)'},
        {'url': 'https://ballerleague.uk/en', 'name': 'Baller League UK: YouTube-Livestream des 5. Spieltags'},
    ],
    'channelLinks': {'Baller League UK (YouTube)': 'https://www.youtube.com/watch?v=ksD12WtlRv0'},
}, {
    'date': '2026-11-09', 'time': '21:05',
    'competition': 'Baller League UK', 'country': 'England',
    'home': 'Deportrio', 'away': 'VZN FC',
    'channels': ['Baller League UK (YouTube)'],
    'sources': [
        {'url': 'https://ballerleague.uk/en/game/241', 'name': 'Baller League UK: offizielle Ansetzung (in Berliner Zeit umgerechnet)'},
        {'url': 'https://ballerleague.uk/en', 'name': 'Baller League UK: YouTube-Livestream des 5. Spieltags'},
    ],
    'channelLinks': {'Baller League UK (YouTube)': 'https://www.youtube.com/watch?v=ksD12WtlRv0'},
}, {
    'date': '2026-11-09', 'time': '22:00',
    'competition': 'Baller League UK', 'country': 'England',
    'home': 'NDL FC', 'away': 'RTG FC',
    'channels': ['Baller League UK (YouTube)'],
    'sources': [
        {'url': 'https://ballerleague.uk/en/game/242', 'name': 'Baller League UK: offizielle Ansetzung (in Berliner Zeit umgerechnet)'},
        {'url': 'https://ballerleague.uk/en', 'name': 'Baller League UK: YouTube-Livestream des 5. Spieltags'},
    ],
    'channelLinks': {'Baller League UK (YouTube)': 'https://www.youtube.com/watch?v=ksD12WtlRv0'},
}, {
    'date': '2026-11-09', 'time': '22:50',
    'competition': 'Baller League UK', 'country': 'England',
    'home': 'SDS FC', 'away': 'Wembley Rangers',
    'channels': ['Baller League UK (YouTube)'],
    'sources': [
        {'url': 'https://ballerleague.uk/en/game/243', 'name': 'Baller League UK: offizielle Ansetzung (in Berliner Zeit umgerechnet)'},
        {'url': 'https://ballerleague.uk/en', 'name': 'Baller League UK: YouTube-Livestream des 5. Spieltags'},
    ],
    'channelLinks': {'Baller League UK (YouTube)': 'https://www.youtube.com/watch?v=ksD12WtlRv0'},
}]


AUSTRIAN_WOMEN_COMPETITION = 'Frauen-Bundesliga (Österreich)'
AUSTRIAN_WOMEN_TEAM_NAMES = {
    'FC Blau Weiß Linz/Union Kleinmünchen ♀': 'FC Blau-Weiß Linz/Kleinmünchen ♀',
    'SpG Südburgenland/TSV Hartberg ♀': 'SpG Südburgenland / TSV Hartberg ♀',
    'Linzer ASK ♀': 'LASK ♀',
    'SK Rapid Wien ♀': 'SK Rapid ♀',
}
POSTPONED_FIXTURES = {
    # ÖFB round 13 preview: https://www.oefb.at/oefb/News/AFBL-26-27-Runde-13-Vorschau
    ('2026-11-14', 'https://fussballgucken.info/match/198554/oefb-frauen-bundesliga/'
     'red-bull-salzburg-frauen-fk-austria-wien-frauen'),
}


def fixture_key(fixture):
    def team_key(name):
        normalized = ''.join(c for c in unicodedata.normalize('NFKD', name.casefold())
                             if not unicodedata.combining(c))
        return normalized.removeprefix('fk ').removeprefix('hnk ')
    return fixture['date'], team_key(fixture['home']), team_key(fixture['away'])


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
        # The radio icon belongs to the coverage box heading, not its list items.
        box = a.find_parent(class_='box')
        heading = box.find(['h2', 'h3', 'h4']) if box else None
        if heading and (heading.select_one('.fg-icon-radio') or re.search(r'Radio|Hörfunk|Audio', heading.get_text(' ', strip=True), re.I)):
            continue
        if AUDIO_RX.search(label):
            continue
        label = re.sub(r' HD$', '', label)
        if label.startswith('Sky Go') or label == 'Sky Stream': continue
        if label.startswith('WOW'):
            label = 'WOW (AT)' if 'Austria' in label else 'WOW'
        if label.startswith('Sky (Schweiz)'): label = 'Sky (CH)'
        if label.startswith('Swisscom'): label = 'blue Sport (CH)'
        if label.startswith('DFB.TV') and not label.startswith('DFB.TV+'): label = 'DFB.TV'
        if label.casefold().replace("’", "'").startswith("l'équipe live foot"):
            label = "L'Équipe Live Foot (FR)"
        elif label.casefold().replace("’", "'").startswith("l'équipe"):
            label = "L'Équipe (FR)"
        if label in {'20', '20 (Mediaset)', '20 (Livestream)'}:
            label = 'Mediaset Infinity (IT)' if label.endswith('(Livestream)') else 'Canale 20 (IT)'
        elif label in {'TV8', 'Cielo'}:
            label += ' (IT)'
        elif label in {'TV8 (Livestream)', 'Cielo (Livestream)'}:
            label = label.replace(' (Livestream)', ' (IT, Livestream)')
        if label.startswith('DAZN'): label = DAZN_REGION_LABELS.get(label, 'DAZN')
        elif label.startswith('MagentaSport'): label = 'MagentaSport'
        elif label.startswith('OneFootball'): label = 'OneFootball'
        elif label.startswith('Disney+'): label = 'Disney+'
        elif label.startswith('Apple TV'): label = 'Apple TV'
        elif label.startswith('FIFA+'): label = 'FIFA+'
        elif label.startswith('Sportdigital+'): label = 'Sportdigital+'
        elif label.startswith('blue Sport'): label = 'blue Sport (CH)'
        elif label.startswith('blue Zoom'): label = 'blue Zoom (CH)'
        elif label in {'ÖFB TV', 'ÖFB TV (via ÖFB App)'}: label = 'ÖFB TV (AT)'
        elif label.lower() == 'orf sport+': label = 'ORF SPORT+ (AT)'
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
        if 'DAZN' in c and c not in DAZN_REGION_LINKS: group = 'dazn'
        elif re.search(r'Sky|WOW', c, re.I) and '(AT)' not in c and '(CH)' not in c: group = 'sky'
        elif 'Prime' in c: group = 'prime'
        elif c in {'Pluto TV', 'DynamoTV (YouTube)', 'Greuther Fürth (YouTube)', 'FCEnergieTV (YouTube)', 'Baller League UK (YouTube)'}: group = 'free'
        # Only explicit German public/free services, never infer from OneFootball.
        elif re.match(r'^(?:ARD|Das Erste|ZDF|BR24|BR \(|WDR|NDR|MDR|SWR|RBB|rbb|hr |[Ss][Pp][Oo][Rr][Tt]1$|RTL$|FIFA\+)', c): group = 'free'
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
        if (date, match_url) in POSTPONED_FIXTURES:
            return None
        home_name = home.get_text(' ', strip=True)
        away_name = away.get_text(' ', strip=True)
        if competition == 'ÖFB Frauen Bundesliga':
            competition = AUSTRIAN_WOMEN_COMPETITION
            home_name = AUSTRIAN_WOMEN_TEAM_NAMES.get(home_name, home_name)
            away_name = AUSTRIAN_WOMEN_TEAM_NAMES.get(away_name, away_name)
        competition_override = VERIFIED_COMPETITIONS.get((date, match_url))
        if competition_override:
            competition = competition_override[0]
        afcon_qualifier = competition == 'Afrika-Cup' and '2026-11-12' <= date <= '2026-11-17'
        if afcon_qualifier:
            competition = 'Afrika-Cup-Qualifikation'
        detail = fetch(match_url)
        expected_date = dt.date.fromisoformat(date).strftime('%d.%m.%Y')
        if not detail.h1 or expected_date not in detail.h1.get_text(' ', strip=True):
            raise ValueError(f'{date}: wrong date on match detail: {match_url}')
        coverage = detail.select('.list-coverage')
        channels = list(dict.fromkeys(c for section in coverage for c in channels_from(section)))
        excluded = EXCLUDED_BROADCASTS.get((date, match_url), ())
        channels = [c for c in channels if c not in excluded]
        researched = VERIFIED_BROADCASTS.get((date, match_url))
        if researched:
            if 'home' in researched:
                home_name = researched['home']
            channels = list(dict.fromkeys(
                [c for c in channels if 'unbekannt' not in c.lower()]
                + researched['channels']))
        if not channels:
            print(f'{date}: skipping entry without confirmed video broadcast: {match_url}', flush=True)
            return None
        kickoff = VERIFIED_KICKOFFS.get(match_url)
        fixture_date = kickoff[0] if kickoff else date
        if kickoff:
            time = kickoff[1]
        # Sachsenpokal: BSC Freiberg, not the Southwest club SGV Freiberg.
        if (date, match_url) == ('2026-11-14', 'https://fussballgucken.info/match/197298/landespokal-sachsen/sgv-freiberg-sg-taucha-99'):
            home_name = 'BSC Freiberg'
        flag = item.select_one('.meta-flag a')
        country = flag.get('title', '').removeprefix('Länderseite ').strip() if flag else 'International'
        channel_links = {c: DAZN_REGION_LINKS[c] for c in channels if c in DAZN_REGION_LINKS}
        if researched:
            channel_links.update(researched.get('channelLinks', {}))
        groups = groups_for(channels)
        if researched and researched.get('freeChannels', set()).intersection(channels) and 'free' not in groups:
            groups.append('free')
        return dict(date=fixture_date, time=time, competition=competition, country=country or 'International',
                         home=home_name, away=away_name,
                         channels=channels, groups=groups,
                         sources=[{'url':url,'name':f'fußballgucken.info – Tagesplan {date}'},
                                  {'url':match_url,'name':'Übertragungsdetails'}]
                                 + ([{'url':kickoff[2], 'name':'Offizielle Anstoßzeit (Europe/Berlin)'}]
                                    if kickoff else [])
                                 + ([{'url':AFCON_QUALIFIER_SCHEDULE, 'name':'CAF – offizieller Spielplan der Qualifikation'}]
                                    if afcon_qualifier and (not kickoff or kickoff[2] != AFCON_QUALIFIER_SCHEDULE) else [])
                                 + ([{'url':competition_override[1], 'name':'Offizielle Wettbewerbszuordnung'}]
                                    if competition_override else [])
                                 + ([{'url':researched['url'], 'name':researched['name']}]
                                    + researched.get('additionalSources', []) if researched else []),
                         verifiedAt=dt.datetime.now(dt.timezone.utc).isoformat(),
                         **({'channelLinks': channel_links} if channel_links else {}))
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
    # Official rescheduling may move a listing beyond the rolling window.
    rows = [g for g in rows if g['date'] in dates]
    known = {fixture_key(g): g for g in rows}
    for fixture in VERIFIED_ADDITIONAL_FIXTURES:
        if fixture['date'] not in dates:
            continue
        key = fixture_key(fixture)
        current = known.get(key)
        if current is None:
            current = dict(fixture, groups=groups_for(fixture['channels']),
                           verifiedAt=dt.datetime.now(dt.timezone.utc).isoformat())
            rows.append(current)
            known[key] = current
        else:
            current['channels'] = list(dict.fromkeys(
                [c for c in current['channels'] if 'unbekannt' not in c.lower()] + fixture['channels']))
            current['groups'] = groups_for(current['channels'])
            current['sources'] += [s for s in fixture['sources'] if s not in current['sources']]
            if fixture.get('channelLinks'):
                current['channelLinks'] = {**current.get('channelLinks', {}), **fixture['channelLinks']}
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
            links = {**previous.get('channelLinks', {}), **g.get('channelLinks', {})}
            if links:
                g['channelLinks'] = {c: link for c, link in links.items() if c in g['channels']}
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(target)

if __name__ == '__main__': main()
