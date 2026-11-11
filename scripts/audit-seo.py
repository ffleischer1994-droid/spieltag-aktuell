"""Fail the build if SEO discovery files contradict generated pages."""
import datetime as dt
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT=Path(__file__).resolve().parent.parent
BASE="https://spieltagaktuell.de"
errors=[]
robots=(ROOT/"robots.txt").read_text()
if f"Sitemap: {BASE}/sitemap.xml" not in robots: errors.append("robots.txt has no correct sitemap declaration")
if re.search(r"(?im)^Disallow:\s*/\s*$",robots): errors.append("robots.txt disallows site root")
tree=ET.parse(ROOT/"sitemap.xml")
ns={"s":"http://www.sitemaps.org/schemas/sitemap/0.9"}
urls=[x.text for x in tree.findall(".//s:loc",ns)]
if not urls or len(set(urls))!=len(urls): errors.append("Sitemap empty or contains duplicate canonical URLs")
match_pages=0
for url in urls:
    if not url.startswith(BASE+"/"): errors.append(f"External URL in sitemap: {url}");continue
    path=unquote(urlsplit(url).path).strip("/")
    file=ROOT/path/"index.html" if path else ROOT/"index.html"
    if not file.is_file(): errors.append(f"Sitemap URL has no index.html: {url}");continue
    html=file.read_text()
    if re.search(r'<meta\s+name="robots"\s+content="noindex',html,re.I): errors.append(f"noindex page in sitemap: {url}")
    m=re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"',html,re.I)
    if not m or m.group(1)!=url: errors.append(f"Canonical URL mismatch: {url}")
    if path.startswith("spiel/"): match_pages+=1
if match_pages==0: errors.append("No match pages included in sitemap")
today=dt.datetime.now(dt.timezone.utc).date()
# A sitemap without recently upcoming games does not serve the core search intent.
future=0
for url in urls:
    path=urlsplit(url).path
    if not path.startswith("/spiel/"): continue
    match=re.search(r"(20\d{2}-\d\d-\d\d)/$",path)
    if match and today<=dt.date.fromisoformat(match.group(1))<=today+dt.timedelta(days=7): future+=1
if future<5: errors.append(f"Too few upcoming games in sitemap (found {future})")
print(f"SEO audit: {len(urls)} canonical URLs, {match_pages} match pages, {future} upcoming match pages")
if errors:
    for error in errors[:30]:print("::error::"+error)
    sys.exit(1)
