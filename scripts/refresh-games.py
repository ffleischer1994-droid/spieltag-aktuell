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


# Official fixture confirmation takes precedence over a conflicting listing time.
VERIFIED_KICKOFFS = {
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


# Researched video coverage missing from the listing; date-scoped and sourced.
VERIFIED_BROADCASTS = {
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
    'date': '2026-11-11', 'time': '14:00',
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
    'channels': ['ÖFB TV (AT)'],
    'sources': [
        {'url': 'https://www.oefb.tv/de/live', 'name': 'ÖFB TV: offizieller Livestream-Spielplan'},
        {'url': 'https://www.oefb.at/oefb/News/AFBL-Spielplan-2026-27-News', 'name': 'Offizieller Spielplan'},
    ],
    'channelLinks': {'ÖFB TV (AT)': 'https://www.oefb.tv/de/live'},
}, {
    'date': '2026-11-14', 'time': '14:00',
    'competition': 'Frauen-Bundesliga (Österreich)', 'country': 'Österreich',
    'home': 'SKN St. Pölten ♀', 'away': 'LASK ♀',
    'channels': ['ÖFB TV (AT)'],
    'sources': [
        {'url': 'https://www.oefb.tv/de/live', 'name': 'ÖFB TV: offizieller Livestream-Spielplan'},
        {'url': 'https://www.oefb.at/oefb/News/AFBL-Spielplan-2026-27-News', 'name': 'Offizieller Spielplan'},
    ],
    'channelLinks': {'ÖFB TV (AT)': 'https://www.oefb.tv/de/live'},
}, {
    'date': '2026-11-14', 'time': '15:00',
    'competition': 'Frauen-Bundesliga (Österreich)', 'country': 'Österreich',
    'home': 'FC Red Bull Salzburg ♀', 'away': 'FK Austria Wien ♀',
    'channels': ['ÖFB TV (AT)'],
    'sources': [
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
    'channels': ['ÖFB TV (AT)'],
    'sources': [
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


def fixture_key(fixture):
    def team_key(name):
        normalized = ''.join(c for c in unicodedata.normalize('NFKD', name.casefold())
                             if not unicodedata.combining(c))
        return normalized.removeprefix('fk ')
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
        elif c in {'Pluto TV', 'DynamoTV (YouTube)', 'Baller League UK (YouTube)'}: group = 'free'
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
            home.string = 'BSC Freiberg'
        flag = item.select_one('.meta-flag a')
        country = flag.get('title', '').removeprefix('Länderseite ').strip() if flag else 'International'
        groups = groups_for(channels)
        if researched and researched.get('freeChannels', set()).intersection(channels) and 'free' not in groups:
            groups.append('free')
        return dict(date=fixture_date, time=time, competition=competition, country=country or 'International',
                         home=home.get_text(' ', strip=True), away=away.get_text(' ', strip=True),
                         channels=channels, groups=groups,
                         sources=[{'url':url,'name':f'fußballgucken.info – Tagesplan {date}'},
                                  {'url':match_url,'name':'Übertragungsdetails'}]
                                 + ([{'url':kickoff[2], 'name':'Offizielle Anstoßzeit (Europe/Berlin)'}]
                                    if kickoff else [])
                                 + ([{'url':researched['url'], 'name':researched['name']}]
                                    + researched.get('additionalSources', []) if researched else []),
                         verifiedAt=dt.datetime.now(dt.timezone.utc).isoformat(),
                         **({'channelLinks': researched['channelLinks']}
                            if researched and 'channelLinks' in researched else {}))
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
