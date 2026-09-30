import fs from "node:fs";
import { chromium } from "playwright";
if(!fs.existsSync("social-output/today.json")) process.exit(0);
const {date,highlights}=JSON.parse(fs.readFileSync("social-output/today.json","utf8"));
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const pretty=date.split("-").reverse().join(".");
function hydrate(path){
 let html=fs.readFileSync(path,"utf8").replace("{{DATE}}",pretty);
 const block=highlights.map(g=>'<article class="game"><div class="time">'+esc(g.time)+' Uhr</div><div class="teams">'+esc(g.home)+' – '+esc(g.away)+'</div><div class="sender">'+esc(g.channels.join(" · "))+'</div></article>').join("");
 html=html.replace(/<!-- Repeat \.game only for verified highlight matches\. No club logos\. -->[\s\S]*?<article class="game">[\s\S]*?<\/article>/,block);
 html=html.replace('src="/logo.svg"','src="'+new URL("../../logo.svg",import.meta.url).href+'"');
 return html;
}
const browser=await chromium.launch({headless:true});
for(const [name,path,w,h] of [["feed","social/instagram-feed-master.html",1080,1350],["story","social/instagram-story-master.html",1080,1920]]){
 const page=await browser.newPage({viewport:{width:w,height:h},deviceScaleFactor:1});
 await page.setContent(hydrate(path),{waitUntil:"networkidle"});
 await page.evaluate(()=>document.fonts.ready);
 await page.screenshot({path:"social-output/"+name+".png",type:"png",fullPage:false});
}
await browser.close();
console.log("Rendered locked HTML masters via Chromium");
