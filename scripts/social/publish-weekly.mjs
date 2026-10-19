import fs from "node:fs";
import { chromium } from "playwright";
import { activeToken } from "./instagram-token.mjs";
const mode=process.env.WEEKLY_FORMAT;
if(!["free-tv","weekend","women"].includes(mode))throw Error("Set WEEKLY_FORMAT to free-tv or weekend");
const zone="Europe/Berlin";
const parts=Object.fromEntries(new Intl.DateTimeFormat("en-GB",{timeZone:zone,year:"numeric",month:"2-digit",day:"2-digit",weekday:"long",hour:"2-digit",hourCycle:"h23"}).formatToParts(new Date()).map(x=>[x.type,x.value]));
const localDate=parts.year+"-"+parts.month+"-"+parts.day;
const desired=mode==="weekend"?"Friday":"Monday",hour=mode==="free-tv"?17:mode==="women"?12:15;
if(process.env.GITHUB_EVENT_NAME==="schedule"&&(parts.weekday!==desired||Number(parts.hour)<hour||Number(parts.hour)>=hour+2)){console.log("Outside Berlin publishing window");process.exit(0)}
const plus=(day,n)=>{let d=new Date(day+"T12:00:00Z");d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10)};
// Always show Friday–Sunday for weekend posts, even when manually previewed earlier in the week.
const weekendFriday=()=>{
 const base=new Date(localDate+"T12:00:00Z");
 const weekday=base.getUTCDay(); // Sunday=0, Friday=5
 const offset=weekday===0?-2:weekday===6?-1:(5-weekday);
 return plus(localDate,offset);
};
const periodStart=mode==="weekend"?weekendFriday():localDate;
// Free-TV previews cover the entire calendar week (Monday through Sunday).
const dates=Array.from({length:mode==="weekend"?3:7},(_,i)=>plus(periodStart,i));
const cover="social/weekly-assets/"+(mode==="free-tv"?"free-tv-keyvisual.png":mode==="women"?"women-keyvisual.png":"weekend-keyvisual (1).png");
if(!fs.existsSync(cover))throw Error("Missing approved ORIGINAL cover: "+cover);
const valid=g=>g?.date&&g?.time&&g?.home&&g?.away&&Array.isArray(g.channels)&&g.channels.length&&!g.channels.some(c=>/unbekannt|option|tba|noch offen/i.test(c));
const selections=mode==="women"?JSON.parse(fs.readFileSync("social/weekly-assets/women-selections.json","utf8")):null;
const allGames=JSON.parse(fs.readFileSync("games.json","utf8"));
const womenCandidate=g=>/frauen|women|wfc|juniorinnen|femeni|féminin/i.test([g.home,g.away,g.competition].join(" "))||/♀/.test(g.home+" "+g.away);
const womenScore=g=>{const t=(g.home+" "+g.away).toLowerCase();let score=0;if(/bayern/.test(t))score+=180;if(/deutschland/.test(t))score+=160;if(/wolfsburg|frankfurt|arsenal|chelsea|barcelona|manchester|lyon|union berlin|hsv|hamburger sv|leipzig/.test(t))score+=80;if(/bundesliga|champions league|wm|world cup|nationalmannschaft/i.test(g.competition||""))score+=55;return score};
const curated=mode==="women"&&selections.weekStart===periodStart&&selections.weekEnd===plus(periodStart,6);
const games=mode==="women"?(curated?selections.matches.map(g=>({...g,home:g.displayHome||g.home,away:g.displayAway||g.away})):allGames.filter(g=>womenCandidate(g)&&valid(g)).sort((a,b)=>womenScore(b)-womenScore(a)).slice(0,5)):allGames;
// Only German-market free-to-air television and freely accessible official streams.
// A "free" group can coexist with paid channels; never print the paid alternatives.
const freeChannel=c=>{
 const name=String(c).trim();
 if(/RTL\+|DAZN|Sky|Magenta|Disney\+|Amazon|Prime Video|blue Sport|OneFootball/i.test(name))return false;
 if(/\((?:AT|CH)\)/i.test(name))return false;
 return /^(?:ARD|Das Erste|ARD Mediathek|ZDF|ZDFheute|ZDFmediathek|RTL(?: HD)?$|Nitro|Sat\.?1|ProSieben|Sport1|3sat|Arte|One(?:\s|$)|WDR|NDR|BR24?\b|BR24Sport|MDR|SWR|RBB|HR(?:\s|$)|DF1|DFB\.TV|DFB \(YouTube\)|DFB \(YouTube\)|DFB TV)(?:\b|$)/i.test(name);
};
const freeChannels=g=>g.channels.filter(freeChannel);
const isFree=g=>freeChannels(g).length>0;
const traditional=/Schalke|Hamburger SV|HSV|Werder Bremen|VfB Stuttgart|1\. FC Köln|FC St\. Pauli|Kaiserslautern|Nürnberg|Hertha BSC|Bochum|Hannover 96|Dynamo Dresden|Arminia Bielefeld|1860 München|Rot-Weiss Essen|Hansa Rostock|Alemannia Aachen|Magdeburg|Karlsruher SC|Eintracht Braunschweig|Fortuna Düsseldorf|Preußen Münster|MSV Duisburg|Borussia Mönchengladbach|Borussia Dortmund|Eintracht Frankfurt|Union Berlin|Bayer 04 Leverkusen|FC Bayern München/i;
const score=g=>{
 const teams=g.home+" "+g.away, competition=g.competition||"";
 let s=0;
 if(g.country==="Deutschland")s+=70;
 if(/^(Bundesliga|2\. Bundesliga)$/.test(competition))s+=160;
 else if(/^(3\. Liga|Frauen-Bundesliga|DFB-Pokal)$/.test(competition))s+=105;
 else if(/Champions League|Europa League|Conference League|Nations League|WM-Qualifikation/i.test(competition))s+=105;
 else if(/Premier League|Serie A|La Liga/i.test(competition))s+=45;
 if(traditional.test(teams))s+=125;
 if(/Deutschland|Nationalmannschaft/i.test(teams))s+=90;
 if(/Saudi|Arabia|Al-Nassr|Al-Hilal/i.test(teams+" "+competition))s-=180;
 return s;
};
const byDate=dates.map(date=>{
 const candidates=games.filter(g=>g.date===date&&valid(g)&&(mode==="weekend"||mode==="women"||isFree(g)));
 const selected=mode==="weekend"
 ?candidates.filter(g=>score(g)>=95).sort((a,b)=>score(b)-score(a)||a.time.localeCompare(b.time)).slice(0,5)
 :candidates.map(g=>({...g,channels:freeChannels(g)}));
 return {date,games:selected.sort((a,b)=>a.time.localeCompare(b.time))};
});
if(!byDate.some(d=>d.games.length))throw Error("No verified matches for "+mode+" "+localDate);
if(mode==="women"&&(byDate.reduce((n,d)=>n+d.games.length,0)<4||byDate.reduce((n,d)=>n+d.games.length,0)>5))throw Error("Women selection must contain 4-5 verified matches");
const caption=mode==="women"?"Frauenfußball diese Woche":mode==="free-tv"?"Fußball im Free-TV diese Woche":"Fußballhighlights am Wochenende";
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const days=["Sonntag","Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag"];
const label=d=>{const v=new Date(d+"T12:00:00Z");return days[v.getUTCDay()]+", "+d.slice(8,10)+"."+d.slice(5,7)+"."};
const logo="data:image/svg+xml;base64,"+fs.readFileSync("logo.svg").toString("base64");
const css=fs.readFileSync("social/instagram-feed-master.html","utf8").match(/<style>([\s\S]*?)<\/style>/)?.[1]||"";
const extra='.post{overflow:hidden}.content{justify-content:center;min-height:0;overflow:visible}.day-group{break-inside:avoid;page-break-inside:avoid;flex-shrink:0}.day-group+.day-group{margin-top:20px}.date{margin:0 0 18px}.game{padding:13px 0 14px}.game .sender{margin-top:5px}.content h1{margin-bottom:30px;flex-shrink:0}';
const row=g=>'<article class="game"><div class="time">'+esc(g.time)+' Uhr</div><div class="teams">'+esc(g.home)+' – '+esc(g.away)+'</div><div class="sender">'+esc(g.channels.join(" · "))+'</div></article>';
const block=day=>'<section class="day-group"><div class="date">'+esc(label(day.date))+'</div><div class="games">'+day.games.map(row).join("")+'</div></section>';
const daysWithGames=byDate.filter(d=>d.games.length);
const fullHtml=(blocks,heading)=>'<!doctype html><html lang="de"><head><meta charset="utf-8"><link href="https://fonts.googleapis.com/css2?family=Archivo+Black&family=Roboto:wght@400;500;700;900&display=swap" rel="stylesheet"><style>'+css+extra+'</style></head><body><main class="post"><img class="logo" src="'+logo+'"><section class="content">'+(heading?'<h1>'+ (mode==="women"?"FRAUENFUSSBALL<br>DIESE WOCHE":mode==="free-tv"?"FREE-TV-<br>HIGHLIGHTS<br>DIESE WOCHE":"WOCHENEND-<br>HIGHLIGHTS")+'</h1>':"")+blocks.map(block).join("")+'</section><footer class="footer">SPIELTAGAKTUELL.DE</footer></main></body></html>';
fs.mkdirSync("social-output/weekly",{recursive:true});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1080,height:1350},deviceScaleFactor:1});
const validateLayout=async (blocks,heading)=>{
 await page.setContent(fullHtml(blocks,heading),{waitUntil:"networkidle"});
 await page.evaluate(()=>document.fonts.ready);
 return page.evaluate(()=>{
  const rect=s=>document.querySelector(s).getBoundingClientRect();
  const post=rect(".post"),logo=rect(".logo"),content=rect(".content"),footer=rect(".footer");
  const groups=[...document.querySelectorAll(".day-group")];
  const headingEl=document.querySelector("h1");
  const safeBottom=1265; // 85px breathing room, independent of a displaced footer
  const errors=[];
  if(post.bottom>1350||footer.bottom>1320||footer.top<1190)errors.push("Footer outside safe area");
  if(content.bottom>footer.top-25||content.scrollHeight>content.clientHeight+2)errors.push("Content exceeds available flex region");
  if(headingEl){let r=headingEl.getBoundingClientRect();if(r.top<logo.bottom+16||r.bottom>safeBottom)errors.push("Heading intersects safe area")}
  groups.forEach((g,i)=>{
   const r=g.getBoundingClientRect();
   if(r.left<85||r.right>995||r.top<logo.bottom+12||r.bottom>Math.min(safeBottom,footer.top-25))errors.push("Day "+i+" outside safe area");
   if(i&&r.top<groups[i-1].getBoundingClientRect().bottom+12)errors.push("Days overlap");
   for(const item of g.querySelectorAll(".game"))if(item.getBoundingClientRect().bottom>r.bottom+2)errors.push("Game clipped within day");
  });
  return {ok:errors.length===0,errors};
 });
};
const fits=async(blocks,heading)=>(await validateLayout(blocks,heading)).ok;
const pages=[];let buffer=[],first=true;
for(const day of daysWithGames){
 if(await fits([...buffer,day],first)){buffer.push(day);continue}
 if(buffer.length){pages.push({days:buffer,heading:first});first=false;buffer=[]}
 if(!await fits([day],first))throw Error("One full day cannot fit on a slide: "+day.date+" ("+day.games.length+" games). Manual review required; no day will be split.");
 buffer=[day];
}
if(buffer.length)pages.push({days:buffer,heading:first});
const coverData=fs.readFileSync(cover);
const displayDate=d=>d.slice(8,10)+"."+d.slice(5,7)+"."+d.slice(2,4);
const dateText=displayDate(dates[0])+" - "+displayDate(dates.at(-1));
const coverPage=await browser.newPage({viewport:{width:1080,height:1350},deviceScaleFactor:1});
const coverHTML='<!doctype html><html><head><meta charset="utf-8"><style>*{box-sizing:border-box}html,body{margin:0;width:1080px;height:1350px;overflow:hidden}body{background:#F2AFC0;position:relative}.visual{position:absolute;inset:0;width:1080px;height:1350px;object-fit:contain;mix-blend-mode:multiply}.pill{position:absolute;left:281px;top:1195px;width:518px;height:74px;border:4px solid #000;border-radius:100px;background:#F2AFC0;display:flex;align-items:center;justify-content:center;font:700 39px Arial,sans-serif;color:#000;letter-spacing:1px}</style></head><body><img class="visual" src="data:image/png;base64,'+coverData.toString("base64")+'"><div class="pill">'+dateText+'</div></body></html>';
await coverPage.setContent(coverHTML,{waitUntil:"load"});
await coverPage.screenshot({path:"social-output/weekly/00.jpg",type:"jpeg",quality:95});
await coverPage.close();
for(let i=0;i<pages.length;i++){const check=await validateLayout(pages[i].days,pages[i].heading);if(!check.ok)throw Error("Refusing to render clipped slide "+i+": "+check.errors.join(", "));await page.screenshot({path:"social-output/weekly/"+String(i+1).padStart(2,"0")+".jpg",type:"jpeg",quality:95})}
await browser.close();
const slideFiles=Array.from({length:pages.length+1},(_,i)=>"social-output/weekly/"+String(i).padStart(2,"0")+".jpg");
if(slideFiles.length>10)throw Error("Instagram allows at most 10 carousel items");
const repost=process.env.WEEKLY_REPOST==="1";
const finalRepost=process.env.WEEKLY_FINAL_REPOST==="1";
if(repost&&finalRepost)throw Error("Repost modes are mutually exclusive");
if((repost||finalRepost)&&(mode!=="free-tv"||localDate!=="2026-10-12"||process.env.GITHUB_EVENT_NAME!=="workflow_dispatch"))throw Error("Repost only authorized for 2026-10-12 free-tv");
const suffix=finalRepost?"-full-week":repost?"-corrected":"";
const publishedPath="social/published/"+mode+"-"+localDate+suffix+".json";
if(fs.existsSync(publishedPath)){const state=JSON.parse(fs.readFileSync(publishedPath,"utf8"));if(state.id){console.log("Already published "+state.id);process.exit(0)}if(state.attempted)throw Error("Previous publish uncertain. Manual review required.");}
if(process.env.WEEKLY_DRY_RUN==="1"){console.log(JSON.stringify({mode,dates,pages:pages.map(x=>x.days.map(d=>d.date)),slides:slideFiles},null,2));process.exit(0)}
const token=activeToken();if(!token)throw Error("Instagram token missing");
const api="https://graph.instagram.com";
const get=async url=>{let r=await fetch(url);if(!r.ok)throw Error(await r.text());return r.json()};
const post=async (url,data)=>{let r=await fetch(url,{method:"POST",headers:{"content-type":"application/x-www-form-urlencoded"},body:new URLSearchParams({...data,access_token:token})});if(!r.ok)throw Error(await r.text());return r.json()};
const me=await get(api+"/me?fields=user_id,username&access_token="+encodeURIComponent(token)),id=me.user_id||me.id;if(!id)throw Error("No IG account id");
const sha=process.env.IG_ASSET_SHA;if(!sha)throw Error("No committed media asset SHA");
const state={date:localDate,mode};const save=()=>{fs.mkdirSync("social/published",{recursive:true});fs.writeFileSync(publishedPath,JSON.stringify(state,null,2))};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const wait=async cid=>{for(let j=0;j<20;j++){await sleep(3000);let st=await get(api+"/"+cid+"?fields=status_code,status&access_token="+encodeURIComponent(token));if(st.status_code==="FINISHED")return;if(["ERROR","EXPIRED"].includes(st.status_code))throw Error("Media container failed "+JSON.stringify(st))}throw Error("Media container not ready")};
const childIds=[];
for(let i=0;i<slideFiles.length;i++){let url="https://raw.githubusercontent.com/"+process.env.GITHUB_REPOSITORY+"/"+sha+"/social/weekly-generated/"+mode+"-"+localDate+suffix+"-"+String(i).padStart(2,"0")+".jpg";let child=await post(api+"/"+id+"/media",{image_url:url,is_carousel_item:"true"});childIds.push(child.id);await wait(child.id)}
const parent=await post(api+"/"+id+"/media",{media_type:"CAROUSEL",children:childIds.join(","),caption:caption+" ("+dates[0].split("-").reverse().join(".")+" – "+dates.at(-1).split("-").reverse().join(".")+")\nAlle Spiele und Sender: spieltagaktuell.de\n\n#fußball #fußballimtv #spieltagaktuell"});
state.container=parent.id;state.children=childIds;save();await wait(parent.id);
state.attempted=true;save();let result=await post(api+"/"+id+"/media_publish",{creation_id:parent.id});state.id=result.id;save();
let confirmation;
try { confirmation=await get(api+"/"+result.id+"?fields=id,media_type,permalink&access_token="+encodeURIComponent(token)); }
catch (error) { console.warn("Instagram accepted media_publish and returned id; follow-up lookup failed:",String(error)); confirmation={id:result.id}; }
if(confirmation.id!==result.id)throw Error("Instagram returned a mismatched media id");
if(confirmation.media_type&&confirmation.media_type!=="CAROUSEL"&&confirmation.media_type!=="CAROUSEL_ALBUM")console.warn("Unexpected Instagram media_type after successful publish:",confirmation.media_type);
console.log("Instagram media_publish succeeded:",result.id,confirmation.media_type||"type not supplied",confirmation.permalink||"");
