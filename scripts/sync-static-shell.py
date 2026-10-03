#!/usr/bin/env python3
"""Synchronize all public static subpages with the current homepage shell."""
import json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
HOME=(ROOT/"index.html").read_text()

def between(text,start,end):
    a=text.index(start)+len(start)
    b=text.index(end,a)
    return text[a:b]

home_style=between(HOME,"<style>","</style>")
header_start=HOME.index("<header>")
main_start=HOME.index('<main class="wrap">',header_start)
header_shell=HOME[header_start:main_start].replace('src="logo.svg"','src="/logo.svg"')
footer_start=HOME.index('<footer class="site-footer"')
script_start=HOME.index("<script>",footer_start)
footer_shell=HOME[footer_start:script_start]

EXTRA=r"""
/* sa-static-content */
.seo-wrap{max-width:1120px;margin:auto;padding:34px 22px 70px}
.seo-wrap h1,.seo-wrap h2,.seo-wrap .teams{font-family:"Archivo Black",Arial,sans-serif}
.seo-wrap h1{font-size:clamp(34px,6vw,62px);line-height:1.02;margin:20px 0 22px;overflow-wrap:anywhere}
.seo-wrap h2{font-size:clamp(22px,4vw,31px);line-height:1.12;overflow-wrap:anywhere}
.seo-wrap p,.seo-wrap li{line-height:1.6}
.seo-wrap>.intro{max-width:850px;font-size:18px}
.seo-wrap>a:first-child{display:inline-block;border:1px solid var(--ink);border-radius:999px;padding:7px 11px;text-decoration:none;font-size:12px;font-weight:900;margin-bottom:4px}
.seo-wrap .links{display:flex;gap:8px;flex-wrap:wrap;margin:22px 0}
.seo-wrap .links a,.seo-wrap .pill{border:1px solid var(--ink);border-radius:999px;padding:8px 12px;text-decoration:none;font-weight:900;font-size:13px;max-width:100%;overflow-wrap:anywhere;background:transparent}
.seo-wrap .links a:hover{background:var(--ink);color:var(--bg)}
.seo-wrap .box{border:1px solid var(--ink);border-radius:18px;padding:22px;margin:22px 0;overflow-wrap:anywhere}
.seo-wrap .game{border-color:var(--ink)}
.seo-wrap .badge{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.seo-wrap .badge:hover{background:var(--bg);color:var(--ink)}
body.dark-mode .seo-wrap .badge{background:var(--pink);color:#000;border-color:var(--pink)}
body.dark-mode .seo-wrap .badge:hover{background:#000;color:var(--pink)}
@media(max-width:560px){.seo-wrap{padding:26px 12px 52px}.seo-wrap h1{font-size:clamp(32px,11vw,48px)}}
"""

SHELL_JS=r"""
(()=>{
 const body=document.body,themeBtn=document.getElementById("theme-btn"),menuBtn=document.getElementById("menu-btn"),menuPanel=document.getElementById("menu-panel"),siteSearch=document.getElementById("site-search"),siteHeader=document.querySelector("header");
 function setTheme(dark){
  body.classList.toggle("dark-mode",dark);
  if(themeBtn){
   themeBtn.setAttribute("aria-pressed",String(dark));
   themeBtn.setAttribute("aria-label",dark?"Light Mode aktivieren":"Dark Mode aktivieren");
  }
  localStorage.setItem("sa-theme",dark?"dark":"light");
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content",dark?"#000000":"#F2AFC0");
 }
 setTheme(localStorage.getItem("sa-theme")==="dark");
 themeBtn?.addEventListener("click",()=>setTheme(!body.classList.contains("dark-mode")));
 menuBtn?.addEventListener("click",()=>{
  const open=menuPanel?.classList.toggle("open");
  menuBtn.setAttribute("aria-expanded",String(Boolean(open)));
  menuBtn.setAttribute("aria-label",open?"Menü schließen":"Menü öffnen");
 });
 siteSearch?.addEventListener("pointerdown",e=>{
  if(matchMedia("(max-width:560px)").matches&&!siteSearch.classList.contains("mobile-open")){
   e.preventDefault();siteSearch.classList.add("mobile-open");setTimeout(()=>siteSearch.focus(),0);
  }
 });
 siteSearch?.addEventListener("keydown",e=>{
  if(e.key==="Enter"&&siteSearch.value.trim()){
   location.href="/?search="+encodeURIComponent(siteSearch.value.trim());
  }
  if(e.key==="Escape"){
   siteSearch.value="";siteSearch.classList.remove("mobile-open");siteSearch.blur();
  }
 });
 siteSearch?.addEventListener("blur",()=>setTimeout(()=>{if(matchMedia("(max-width:560px)").matches&&!siteSearch.value)siteSearch.classList.remove("mobile-open")},120));
 function syncHeader(){
  if(!siteHeader)return;
  if(matchMedia("(min-width:851px)").matches)siteHeader.classList.toggle("scrolled",scrollY>24);
  else siteHeader.classList.remove("scrolled");
 }
 syncHeader();addEventListener("scroll",syncHeader,{passive:true});addEventListener("resize",syncHeader);
 if("serviceWorker" in navigator)navigator.serviceWorker.register("/sw.js").catch(()=>{});
})()
"""

config=json.loads((ROOT/"seo/config.json").read_text())
registry=json.loads((ROOT/"seo/matches.json").read_text()) if (ROOT/"seo/matches.json").exists() else {}
targets={
    "vereine","sender","ueber","datenquellen","impressum","datenschutz",
    *[c["path"].strip("/") for c in config],
    *[x["path"].strip("/") for x in registry.values()],
}

updated=0
for rel in sorted(targets):
    if rel in {"","gaestebuch"}: continue
    p=ROOT/rel/"index.html"
    if not p.exists(): continue
    text=p.read_text()
    if "<body" not in text or "<main" not in text: continue

    old_style=re.search(r"<style>([\s\S]*?)</style>",text)
    if not old_style: continue
    css=re.sub(r"/\* sa-shell:start \*/[\s\S]*?/\* sa-shell:end \*/","",old_style.group(1)).strip()
    merged=css+"\n/* sa-shell:start */\n"+home_style+"\n"+EXTRA+"\n/* sa-shell:end */"
    text=text[:old_style.start(1)]+merged+text[old_style.end(1):]

    body_pos=text.index("<body")
    body_open_end=text.index(">",body_pos)+1
    main_match=re.search(r"<main\b[^>]*>",text[body_open_end:],re.I)
    if not main_match: continue
    main_open_start=body_open_end+main_match.start()
    main_open_end=body_open_end+main_match.end()
    main_close=text.rfind("</main>")
    if main_close<main_open_end: continue
    inner=text[main_open_end:main_close]
    inner=re.sub(r"<footer class=\"footer\">[\s\S]*?</footer>","",inner,count=1)
    inner=re.sub(r"<nav class=\"footer\">[\s\S]*?</nav>","",inner,count=1)

    text=text[:body_pos]+"<body>"+header_shell+'<main class="seo-wrap">'+inner+"</main>"+footer_shell+"<script>"+SHELL_JS+"</script></body>\n</html>\n"
    p.write_text(text)
    updated+=1

print(f"Synchronized site shell on {updated} static pages")
