import importlib.util
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

spec=importlib.util.spec_from_file_location("refresh",Path(__file__).with_name("refresh-games.py"))
refresh=importlib.util.module_from_spec(spec);spec.loader.exec_module(refresh)

class CoverageTests(unittest.TestCase):
 def test_heading_classifies_whole_radio_section(self):
  soup=BeautifulSoup('''<div class="box"><h3><i class="fg-icon-radio"></i>(Web-)Radio</h3><div class="coverage"><ul class="list-coverage"><li><a href="/sender/new">New club livestream</a></li></ul></div></div><div class="box"><h3>Internet (Livestream)</h3><ul class="list-coverage"><li><a href="/sender/leagues">Leagues</a></li></ul></div>''',"html.parser")
  channels=[c for section in soup.select('.list-coverage') for c in refresh.channels_from(section)]
  self.assertEqual(channels,['Leagues'])
 def test_label_fallback_without_source_markup(self):
  soup=BeautifulSoup('''<ul><li><a href="/sender/asc">ASC-Livestream (Bielefeld)</a></li><li><a href="/sender/fm">EnergieFM</a></li><li><a href="/sender/05">05er.fm</a></li><li><a href="/sender/dfb">DFB.TV</a></li><li><a href="/sender/laola">LAOLA1 (Livestream)</a></li></ul>''',"html.parser")
  self.assertEqual(refresh.channels_from(soup),['DFB.TV','LAOLA1 (Livestream)'])
 def test_real_source_radio_heading(self):
  # Real source structure, including free icons that must not imply free video.
  soup=BeautifulSoup('''<div class="box white gap"><h3><i class="fg-icon fg-icon-radio fg-icon-x5"></i>(Web-)Radio</h3><div class="coverage"><ul class="list list-unstyled list-coverage"><li><a href="/sender/energiefm">EnergieFM</a><span class="fg-icon-free"></span></li></ul></div></div>''',"html.parser")
  self.assertEqual(refresh.channels_from(soup.select_one('.list-coverage')),[])

if __name__=='__main__':unittest.main()
