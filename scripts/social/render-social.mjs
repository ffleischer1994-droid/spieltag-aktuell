import fs from "node:fs";
import { chromium } from "playwright";
if(!fs.existsSync("social-output/today.json")) process.exit(1);
const {date,highlights}=JSON.parse(fs.readFileSync("social-output/today.json","utf8"));
if(!highlights.length||highlights.length>4||highlights.some((g,i)=>g.date!==date||!g.channels?.length||g.channels.some(c=>/unbekannt|option/i.test(c))||(i>0&&g.time<highlights[i-1].time))) throw new Error("Invalid or unsorted highlights");
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const pretty=date.split("-").reverse().join(".");
function hydrate(path){
 let html=fs.readFileSync(path,"utf8").replace("{{DATE}}",pretty);
 const block=highlights.map(g=>'<article class="game"><div class="time">'+esc(g.time)+' Uhr</div><div class="teams">'+esc(g.home)+' – '+esc(g.away)+'</div><div class="sender">'+esc(g.channels.join(" · "))+'</div></article>').join("");
 html=html.replace(/<!-- Repeat \.game only for verified highlight matches\. No club logos\. -->[\s\S]*?<article class="game">[\s\S]*?<\/article>/,block);
 const logoData="data:image/svg+xml;base64,"+fs.readFileSync("logo.svg").toString("base64");
 html=html.replace('src="/logo.svg"','src="'+logoData+'"');
 return html;
}
const browser=await chromium.launch({headless:true});
for(const [name,path,w,h] of [["feed","social/instagram-feed-master.html",1080,1350],["story","social/instagram-story-master.html",1080,1920]]){
 const page=await browser.newPage({viewport:{width:w,height:h},deviceScaleFactor:1});
 await page.setContent(hydrate(path),{waitUntil:"networkidle"});
 await page.evaluate(()=>document.fonts.ready);
 const errors=await page.evaluate(async()=>{
  const errors=[];
  if(!document.fonts.check('30px "Archivo Black"')||!document.fonts.check('22px Roboto'))errors.push('Fonts unavailable');
  const logos=[...document.querySelectorAll('img')];
  if(logos.length!==1||!logos[0].complete||!logos[0].naturalWidth)errors.push('Logo unavailable');
  const elements=[...document.querySelectorAll('.logo,h1,.date,.game,.footer')];
  for(const el of elements){const r=el.getBoundingClientRect();if(r.left<0||r.top<0||r.right>innerWidth||r.bottom>innerHeight||el.scrollWidth>el.clientWidth+1)errors.push('Clipped '+el.className);}
  for(let i=1;i<elements.length;i++){if(elements[i].getBoundingClientRect().top<elements[i-1].getBoundingClientRect().bottom-1)errors.push('Overlapping blocks');}
  return errors;
 });
 if(errors.length)throw new Error(name+': '+errors.join(', '));
 await page.screenshot({path:"social-output/"+name+".png",type:"png",fullPage:false});
 await page.screenshot({path:"social-output/"+name+".jpg",type:"jpeg",quality:95});
 await page.close();
}
fs.writeFileSync("social-output/preflight.json",JSON.stringify({date,passed:true}));
await browser.close();
console.log("Rendered locked HTML masters via Chromium");

