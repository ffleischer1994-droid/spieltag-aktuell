"""Generate useful static search pages from the shared broadcast dataset."""
import argparse, datetime as dt, html, json, re, unicodedata
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parent.parent
BASE='https://spieltagaktuell.de'
E=lambda x:html.escape(str(x),quote=True)
def slug(x):
 x=x.replace('♀','frauen').replace('ß','ss').replace('ä','ae').replace('ö','oe').replace('ü','ue')
 return re.sub(r'[^a-z0-9]+','-',unicodedata.normalize('NFKD',x.lower()).encode('ascii','ignore').decode()).strip('-')
def pretty(x):return dt.date.fromisoformat(x).strftime('%d.%m.%Y')
def url(p):return BASE+'/'+p.strip('/')+'/' if p else BASE+'/'
def key(g):return '|'.join([g['date'],g['home'],g['away']])
def valid(g):return bool(g.get('channels')) and not any(re.search('unbekannt|option',c,re.I) for c in g['channels'])
CSS='''@import url('https://fonts.googleapis.com/css2?family=Archivo+Black&family=Roboto:wght@400;700;900&display=swap');:root{--bg:#F2AFC0;--ink:#000}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px Roboto,Arial,sans-serif}a{color:inherit}header{border-bottom:1px solid var(--ink);background:var(--bg)}.head{max-width:1080px;margin:auto;padding:18px;display:flex;align-items:center;justify-content:center;position:relative}.logo{width:230px;max-width:65vw}.theme{position:absolute;right:18px;border:2px solid var(--ink);border-radius:50%;width:44px;height:44px;background:var(--bg);color:var(--ink);font-size:25px}.wrap{max-width:1080px;margin:auto;padding:30px 22px 65px}h1,h2,.teams{font-family:'Archivo Black',Arial,sans-serif}h1{font-size:clamp(32px,6vw,62px);line-height:1.06;margin:22px 0;overflow-wrap:anywhere}h2{font-size:clamp(23px,4vw,32px);line-height:1.15;overflow-wrap:anywhere}p{line-height:1.6}.intro{max-width:850px;font-size:18px}.status{font-size:14px;line-height:1.6}.links{display:flex;gap:10px;flex-wrap:wrap;margin:22px 0}.links a,.pill{border:1px solid var(--ink);border-radius:999px;padding:9px 14px;text-decoration:none;max-width:100%;overflow-wrap:anywhere}.game{display:grid;grid-template-columns:125px minmax(0,1fr);gap:18px;border-top:1px solid var(--ink);padding:22px 0}.game>div{min-width:0}.when{font-weight:900;line-height:1.6}.teams{font-size:23px;line-height:1.2;overflow-wrap:anywhere}.meta{font-size:14px;line-height:1.5;margin-top:8px;overflow-wrap:anywhere}.providers{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}.badge{background:var(--ink);color:var(--bg);border:1px solid var(--ink);border-radius:999px;padding:7px 11px;font-size:14px;font-weight:900;text-decoration:none;max-width:100%;overflow-wrap:anywhere}.badge:hover{background:var(--bg);color:var(--ink)}.box{border:1px solid var(--ink);border-radius:18px;padding:22px;margin:22px 0;overflow-wrap:anywhere}.facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.fact strong{display:block;font-size:22px;margin-top:7px;overflow-wrap:anywhere}.label{font-size:13px;font-weight:900}.footer{border-top:1px solid var(--ink);padding-top:20px;margin-top:36px}.source{font-size:14px;overflow-wrap:anywhere}@media(min-width:851px){body.dark-mode{--bg:#000;--ink:#F2AFC0}body.dark-mode .logo{filter:brightness(0) saturate(100%) invert(83%) sepia(18%) saturate(1034%) hue-rotate(294deg) brightness(99%) contrast(92%)}}@media(max-width:850px){.theme{display:none}}@media(max-width:560px){.wrap{padding:24px 14px 45px}.game{grid-template-columns:1fr;gap:8px}.facts{grid-template-columns:1fr}.teams{font-size:21px}}'''
THEME="""(()=>{const b=document.querySelector('.theme');const sync=()=>{const dark=matchMedia('(min-width:851px)').matches&&localStorage.getItem('sa-theme')==='dark';document.body.classList.toggle('dark-mode',dark);b.textContent=dark?'☀':'☾';b.setAttribute('aria-label',dark?'Light Mode aktivieren':'Dark Mode aktivieren');b.setAttribute('aria-pressed',String(dark));};b.onclick=()=>{localStorage.setItem('sa-theme',document.body.classList.contains('dark-mode')?'light':'dark');sync()};sync();addEventListener('resize',sync)})()"""

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--today');ap.add_argument('--data-updated');args=ap.parse_args()
 today=dt.date.fromisoformat(args.today) if args.today else dt.datetime.now(ZoneInfo('Europe/Berlin')).date()
 updated=args.data_updated or today.isoformat(); data_date=updated[:10]
 games=json.loads((ROOT/'games.json').read_text());games=sorted(games,key=lambda g:(g['date'],g['time'],g['home'],g['away']))
 for g in games:
  dt.date.fromisoformat(g['date']);dt.time.fromisoformat(g['time']);assert all(g.get(k) for k in ('home','away','competition','country','channels'))
 window=[g for g in games if today.isoformat()<=g['date']<=(today+dt.timedelta(days=6)).isoformat()]
 config=json.loads((ROOT/'seo/config.json').read_text());registry=json.loads((ROOT/'seo/matches.json').read_text()) if (ROOT/'seo/matches.json').exists() else {}
 known={key(g):g for g in window if valid(g)}
 # Keep existing editorial choices; add at most 8 useful, confirmed fixtures per run.
 selected=sorted([g for g in window if valid(g) and (('free' in g.get('groups',[]) and ('Deutschland' in g['home']+' '+g['away'] or 'Bundesliga' in g['competition'])) or (g['competition'].lower().find('bundesliga')>=0 and 'frauen' in (g['competition']+' '+g['home']+' '+g['away']).lower()))],key=lambda g:(g['date'],g['time']))[:8]
 for g in selected:registry.setdefault(key(g),{'path':'spiel/'+slug(g['home'])+'-'+slug(g['away'])+'-'+g['date'],'game':g,'dataUpdated':data_date})
 for k in list(registry):
  if k in known:registry[k]['game']=known[k];registry[k]['dataUpdated']=data_date
 match_links={k:v['path'] for k,v in registry.items() if k in known}
 team_links={c['team']:c['path'] for c in config if c['kind']=='team'}
 written=set()
 def links(items):return '<nav class="links">'+''.join('<a href="/'+p.strip('/')+'/">'+E(t)+'</a>' if p else '<a href="/">'+E(t)+'</a>' for p,t in items)+'</nav>'
 common=[('','Alle Spiele'),('fussball-heute','Heute'),('fussball-morgen','Morgen'),('free-tv','Free-TV'),('free-tv/wochenende','Wochenende'),('vereine','Vereine'),('sender','Sender')]
 def page(path,title,description,body,schema=None,index=True):
  schemas=[{'@context':'https://schema.org','@type':'WebPage','name':title,'url':url(path),'description':description,'inLanguage':'de','publisher':{'@type':'Organization','@id':BASE+'/#organization','name':'Spieltag Aktuell','url':BASE+'/'}},{'@context':'https://schema.org','@type':'BreadcrumbList','itemListElement':[{'@type':'ListItem','position':1,'name':'Spieltag Aktuell','item':BASE+'/'},{'@type':'ListItem','position':2,'name':title,'item':url(path)}]}]
  if schema:schemas.append(schema)
  ld=''.join('<script type="application/ld+json">'+json.dumps(x,ensure_ascii=False).replace('<','\\u003c')+'</script>' for x in schemas)
  text='<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+E(title)+' | Spieltag Aktuell</title><meta name="description" content="'+E(description)+'"><meta name="robots" content="'+('index' if index else 'noindex')+',follow,max-image-preview:large"><link rel="canonical" href="'+url(path)+'"><link rel="icon" href="/favicon.svg"><meta name="theme-color" content="#F2AFC0">'+ld+'<style>'+CSS+'</style></head><body><header><div class="head"><a href="/"><img class="logo" src="/logo.svg" alt="Spieltag Aktuell"></a><button class="theme" type="button" aria-label="Dark Mode aktivieren">☾</button></div></header><main class="wrap"><a href="/">Spieltag Aktuell</a><h1>'+E(title)+'</h1>'+body+'<footer class="footer">'+links(common+[('datenquellen','Daten & Recherche'),('ueber','Über uns'),('impressum','Impressum'),('datenschutz','Datenschutz')])+'</footer></main><script>'+THEME+'</script></body></html>\n'
  p=ROOT/path/'index.html';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);written.add(path+'/index.html')
 def badges(g):
  parts=[]
  for c in g['channels']:
   target=g.get('channelLinks',{}).get(c)
   if target and target.startswith('https://'):parts.append('<a class="badge" href="'+E(target)+'" target="_blank" rel="noopener noreferrer">'+E(c)+' ↗</a>')
   else:
    overview=next((x['path'] for x in config if x['kind']=='sender' and re.search(x['pattern'],c,re.I)),None)
    parts.append('<a class="badge" href="/'+overview+'/" title="Senderübersicht">'+E(c)+'</a>' if overview else '<span class="badge">'+E(c)+'</span>')
  return '<div class="providers">'+''.join(parts)+'</div>'
 def rows(items):
  if not items:return '<div class="box">Im aktuell erfassten Zeitraum ist kein passendes Spiel eingetragen. Das bedeutet nicht, dass außerhalb unseres Datenfensters keine Spiele stattfinden.</div>'
  out=[]
  for g in items:
   name=E(g['home']+' – '+g['away']);p=match_links.get(key(g));name='<a href="/'+p+'/">'+name+'</a>' if p else name
   ts=[(team_links[t],t.replace(' ♀',' Frauen')) for t in (g['home'],g['away']) if t in team_links]
   comp=next((c for c in config if c['kind']=='competition' and re.search(c['pattern'],g['competition'],re.I)),None)
   if comp:ts.append((comp['path'],comp['title']))
   out.append('<article class="game"><div class="when">'+pretty(g['date'])+'<br>'+E(g['time'])+' Uhr</div><div><div class="teams">'+name+'</div><div class="meta">'+E(g['competition']+' · '+g['country'])+'</div>'+badges(g)+(links(ts) if ts else '')+'</div></article>')
  return ''.join(out)
 def status():return '<p class="status">Datenstand: <time datetime="'+E(data_date)+'">'+pretty(data_date)+'</time>. Alle Anstoßzeiten in Europe/Berlin. Erfasst: '+pretty(today.isoformat())+' bis '+pretty((today+dt.timedelta(days=6)).isoformat())+'. Übertragungen können sich kurzfristig ändern. <a href="/datenquellen/">So prüfen wir die Angaben</a>.</p>'
 monday=today-dt.timedelta(days=today.weekday());sunday=monday+dt.timedelta(days=6)
 saturday=monday+dt.timedelta(days=5)
 if today>sunday:saturday+=dt.timedelta(days=7)
 for c in config:
  kind=c['kind'];title=c['title'];intro=c['intro'];items=window
  if kind=='team':items=[g for g in items if c['team'] in (g['home'],g['away'])]
  elif kind=='competition':items=[g for g in items if re.search(c['pattern'],g['competition'],re.I) or (c['path']=='frauenfussball' and '♀' in g['home']+g['away'])]
  elif kind=='sender':items=[g for g in items if any(re.search(c['pattern'],x,re.I) for x in g['channels'])]
  elif kind=='today':items=[g for g in items if g['date']==today.isoformat()]
  elif kind=='tomorrow':items=[g for g in items if g['date']==(today+dt.timedelta(days=1)).isoformat()]
  elif kind=='evening':items=[g for g in items if g['date']==today.isoformat() and g['time']>='17:00']
  if c.get('free'):items=[g for g in items if 'free' in g.get('groups',[])]
  if kind=='week':
   items=[g for g in items if monday.isoformat()<=g['date']<=sunday.isoformat()];intro+=' Kalenderwoche: '+pretty(monday.isoformat())+'–'+pretty(sunday.isoformat())+'. Bereits vergangene Tage sind nicht Teil unserer laufenden Spieldaten.'
  if kind=='weekend':items=[g for g in items if saturday.isoformat()<=g['date']<=sunday.isoformat()];intro+=' Wochenende: '+pretty(saturday.isoformat())+'–'+pretty(sunday.isoformat())+'.'
  if c.get('free'):intro+=' Kostenlos in Deutschland empfangbare Angebote; österreichische und Schweizer Sender allein zählen hier nicht als deutsches Free-TV.'
  body='<p class="intro">'+E(intro)+'</p>'+status()+links(common)+rows(items)
  if kind=='team':body+='<section class="box"><h2>Wo läuft '+E(c['team'].replace(' ♀',' Frauen'))+'?</h2><p>Die Übertragung richtet sich nach der konkreten Partie und dem Wettbewerb. Oben findest du die aktuell erfassten Spiele mit ihren Sendern. Ein leeres Datenfenster ist keine Aussage über spätere Termine.</p><a href="/?team='+E(__import__('urllib.parse',fromlist=['quote']).quote(c['team']))+'">Verein im interaktiven Spielplan öffnen</a></section>'
  schema={'@context':'https://schema.org','@type':'ItemList','itemListElement':[{'@type':'ListItem','position':i+1,'name':g['home']+' – '+g['away'],'url':url(match_links[key(g)]) if key(g) in match_links else BASE+'/?team='+__import__('urllib.parse',fromlist=['quote']).quote(g['home'])} for i,g in enumerate(items)]}
  page(c['path'],title,intro,body,schema)
 for kind,path,title in [('team','vereine','Vereine: Spiele, TV & Stream'),('sender','sender','Fußballsender und Streaminganbieter')]:
  entries=[(c['path'],c['title'].split(':')[0]) for c in config if c['kind']==kind]
  page(path,title,'Wähle eine Übersicht mit aktuell erfassten Fußballspielen, Anstoßzeiten und Übertragungen.','<p class="intro">Wähle eine Übersicht. Die Spielangaben werden aus derselben Datenbasis wie unser täglicher Spielplan erzeugt.</p>'+links(entries)+status())
 for k,v in registry.items():
  g=v['game'];current=k in known;past=g['date']<today.isoformat();name=g['home']+' – '+g['away'];title=name+': TV, Stream & Uhrzeit'
  body=('<p class="box">Archiv: Diese Partie liegt in der Vergangenheit. Die Angaben unten beziehen sich auf den damaligen Datenstand.</p>' if past else '<p class="box">Diese Partie ist im aktuellen Datenfenster nicht bestätigt. Die gespeicherten Angaben können überholt sein.</p>' if not current else '')
  body+='<div class="box facts">'+''.join('<div class="fact"><span class="label">'+l+'</span><strong>'+E(t)+'</strong></div>' for l,t in [('Datum',pretty(g['date'])),('Anstoß',g['time']+' Uhr (Europe/Berlin)'),('Wettbewerb',g['competition']),('Region',g['country'])])+'</div><section class="box"><h2>Wo läuft '+E(name)+'?</h2><p>'+E('Laut unserem '+('aktuellen' if current else 'gespeicherten')+' Datenstand: '+', '.join(g['channels']))+'.</p>'+badges(g)+'</section><section class="box"><h2>Ist das Spiel kostenlos in Deutschland zu sehen?</h2><p>'+('Mindestens ein kostenloses Angebot in Deutschland ist in unseren Spieldaten erfasst. Die Senderliste kann zusätzlich kostenpflichtige oder regionale Angebote enthalten.' if 'free' in g.get('groups',[]) else 'In unseren Spieldaten ist kein kostenloses Angebot für Deutschland bestätigt.')+'</p></section>'
  if current:body+=status()
  elif v.get('dataUpdated'):body+='<p class="status">Gespeicherter Datenstand: '+pretty(v['dataUpdated'])+'</p>'
  if g.get('verifiedAt'):
   try:
    check=dt.datetime.fromisoformat(g['verifiedAt']).astimezone(ZoneInfo('Europe/Berlin'))
    body+='<p class="status">Einzelprüfung dokumentiert: <time datetime="'+E(g['verifiedAt'])+'">'+check.strftime('%d.%m.%Y, %H:%M')+' Uhr</time>.</p>'
   except ValueError:pass
  sources=[(u,'Direkter Anbieterlink: '+c) for c,u in g.get('channelLinks',{}).items() if u.startswith('https://')]
  sources +=[(s['url'],s.get('name','Quelle')) for s in g.get('sources',[]) if isinstance(s,dict) and s.get('url','').startswith('https://')]
  body+='<section class="source"><h2>Quellen und Datenstand</h2><p>Die Übertragungsangaben stammen aus unserem recherchierten Spielplan. <a href="/datenquellen/">Recherche und Korrekturen</a>.</p>'+''.join('<p><a href="'+E(u)+'" rel="noopener noreferrer">'+E(t)+'</a></p>' for u,t in sources)+'</section>'+links([(team_links[t],t.replace(' ♀',' Frauen')) for t in (g['home'],g['away']) if t in team_links])
  start=dt.datetime.fromisoformat(g['date']+'T'+g['time']).replace(tzinfo=ZoneInfo('Europe/Berlin')).isoformat()
  schema={'@context':'https://schema.org','@type':'SportsEvent','name':name,'startDate':start,'sport':'Fußball','url':url(v['path']),'homeTeam':{'@type':'SportsTeam','name':g['home']},'awayTeam':{'@type':'SportsTeam','name':g['away']}}
  page(v['path'],title,name+' am '+pretty(g['date'])+': Anstoß '+g['time']+' Uhr, TV- und Streaminganbieter sowie Informationen zum deutschen Free-TV.',body,schema,index=current)
 (ROOT/'seo/matches.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n')
 # Add generated match links without altering the interactive application.
 p=ROOT/'index.html';text=p.read_text();text=re.sub(r'const MATCH_PAGES=\{[\s\S]*?\};','const MATCH_PAGES='+json.dumps({k:'/'+p+'/' for k,p in match_links.items()},ensure_ascii=False)+';',text)
 if '/fussball-morgen/' not in text:text=text.replace('<a href="/fussball-heute/">Fußball heute</a></div>','<a href="/fussball-heute/">Fußball heute</a><a href="/fussball-morgen/">Fußball morgen</a></div>',1)
 if '/free-tv/wochenende/' not in text:text=text.replace('<a href="/fussball-heute/">Fußball heute</a><a href="/frauenfussball/">','<a href="/fussball-heute/">Fußball heute</a><a href="/fussball-morgen/">Fußball morgen</a><a href="/free-tv/wochenende/">Free-TV am Wochenende</a><a href="/frauenfussball/">',1)
 today_games=[g for g in window if g['date']==today.isoformat()]
 initial=[]
 for g in today_games:
  name=E(g['home']+' – '+g['away']);target=match_links.get(key(g))
  if target:name='<a href="/'+target+'/">'+name+'</a>'
  initial.append('<article class="match"><div class="time">'+E(g['time'])+'</div><div><div class="teams">'+name+'</div><div class="meta">'+E(g['competition']+' · '+g['country'])+'</div></div>'+badges(g).replace('class="providers"','class="providers"')+'</article>')
 initial_html='<div class="time-block"><div class="matches">'+''.join(initial)+'</div></div>' if initial else '<div class="empty-state">Für heute sind im aktuellen Datenstand keine Spiele erfasst.</div>'
 text=re.sub(r'<div id="game-list">[\s\S]*?</div><section id="live-area"','<div id="game-list">'+initial_html+'</div><section id="live-area"',text,count=1)
 text=re.sub(r'<h2 id="selected-date-label">.*?</h2>','<h2 id="selected-date-label">Fußball am '+pretty(today.isoformat())+'</h2>',text,count=1)
 text=re.sub(r'<div class="count" id="count">.*?</div>','<div class="count" id="count">'+str(len(today_games))+' Spiele</div>',text,count=1)
 if '<!-- seo-data-status -->' in text:text=re.sub(r'<!-- seo-data-status -->[\s\S]*?<!-- /seo-data-status -->','<!-- seo-data-status -->'+status()+'<!-- /seo-data-status -->',text,count=1)
 else:text=text.replace('</main>','<!-- seo-data-status -->'+status()+'<!-- /seo-data-status --></main>',1)
 text=text.replace('heute und den nächsten 7 Tagen','heute und den nächsten sechs Tagen')
 if '/vereine/' not in text:text=text.replace('<a href="/ueber/">Über uns</a>','<a href="/vereine/">Vereine</a><a href="/sender/">Senderübersicht</a><a href="/ueber/">Über uns</a>',1)
 p.write_text(text)
 # Only publish indexable public pages; no social previews or expired fixtures.
 urls=[]
 for p in sorted(ROOT.rglob('index.html')):
  relative=p.relative_to(ROOT).as_posix()
  if relative.startswith(('instagram/','social/')):continue
  text=p.read_text()
  if re.search(r'name="robots" content="noindex',text):continue
  canonical=re.search(r'rel="canonical" href="([^"]+)"',text)
  if canonical:urls.append(canonical.group(1))
  elif relative=='index.html':urls.append(BASE+'/')
 (ROOT/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+''.join('  <url><loc>'+E(u)+'</loc></url>\n' for u in sorted(set(urls)))+'</urlset>\n')
 print(f'Generated {len(written)} pages; {len(match_links)} current match pages; {len(set(urls))} sitemap URLs')
if __name__=='__main__':main()
