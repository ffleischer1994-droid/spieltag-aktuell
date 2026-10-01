import json,re,sys,xml.etree.ElementTree as ET
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
root=Path(__file__).resolve().parent.parent
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.canon=[];self.h1=0
 def handle_starttag(self,t,a):
  d=dict(a)
  if t=='h1':self.h1+=1
  if t=='a' and d.get('href','').startswith('/'):self.links.append(d['href'])
  if t=='link' and d.get('rel')=='canonical':self.canon.append(d['href'])
config=json.loads((root/'seo/config.json').read_text());files=[root/c['path']/'index.html' for c in config]+list((root/'spiel').glob('*/index.html'))+[root/'index.html']
for f in files:
 s=f.read_text();p=Parser();p.feed(s)
 assert len(p.canon)==1,(f,'canonical')
 assert p.h1==1 or f==root/'index.html',(f,'h1')
 for href in p.links:
  path=unquote(urlsplit(href).path).strip('/');target=root/path
  assert target.is_file() or (target/'index.html').is_file(),(f,'broken link',href)
 for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>',s,re.S):json.loads(x)
 if f!=root/'index.html' and f.parent.parent.name!='spiel':assert 'fetch(' not in s,(f,'JS-only data')
ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}
urls=[x.text for x in ET.parse(root/'sitemap.xml').findall('.//s:loc',ns)];assert len(urls)==len(set(urls))
for u in urls:
 path=urlsplit(u).path.strip('/');f=root/path/'index.html';assert f.exists(),u
 assert 'content="noindex' not in f.read_text(),u
home=(root/'index.html').read_text();assert '<div id="game-list"><div class="time-block">' in home or 'Für heute sind im aktuellen Datenstand' in home
assert '/fussball-morgen/' in home and '/free-tv/wochenende/' in home
print('PASS: static pages, links, canonical URLs, JSON-LD, sitemap and initial homepage data')
