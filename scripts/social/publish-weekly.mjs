import fs from "node:fs";
import { chromium } from "playwright";
import { activeToken } from "./instagram-token.mjs";
const mode=process.env.WEEKLY_FORMAT;
if(!["free-tv","weekend"].includes(mode))throw Error("Set WEEKLY_FORMAT to free-tv or weekend");
const zone="Europe/Berlin";
const parts=Object.fromEntries(new Intl.DateTimeFormat("en-GB",{timeZone:zone,year:"numeric",month:"2-digit",day:"2-digit",weekday:"long",hour:"2-digit",hourCycle:"h23"}).formatToParts(new Date()).map(x=>[x.type,x.value]));
const localDate=parts.year+"-"+parts.month+"-"+parts.day;
const desired=mode==="free-tv"?"Monday":"Friday",hour=mode==="free-tv"?17:15;
if(process.env.GITHUB_EVENT_NAME==="schedule"&&(parts.weekday!==desired||Number(parts.hour)<hour||Number(parts.hour)>=hour+2)){console.log("Outside Berlin publishing window");process.exit(0)}
const plus=(day,n)=>{let d=new Date(day+"T12:00:00Z");d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10)};
const dates=Array.from({length:mode==="free-tv"?5:3},(_,i)=>plus(localDate,i));
const cover="social/weekly-assets/"+(mode==="free-tv"?"free-tv-cover.png":"weekend-cover.png");
if(!fs.existsSync(cover))throw Error("Missing approved ORIGINAL cover: "+cover);
const games=JSON.parse(fs.readFileSync("games.json","utf8"));
const valid=g=>g?.date&&g?.time&&g?.home&&g?.away&&Array.isArray(g.channels)&&g.channels.length&&!g.channels.some(c=>/unbekannt|option|tba|noch offen/i.test(c));
const isFree=g=>(g.groups||[]).includes("free")||g.channels.some(c=>/^(ARD|Das Erste|ZDF|RTL|Nitro|Sat\.?1|ProSieben|Sport1|3sat|Arte|One|WDR|NDR|BR|MDR|SWR|RBB|HR|ORF|SRF)(\b|$)/i.test(c));
const score=g=>{let s=0,t=(g.home+" "+g.away+" "+(g.competition||""));if(g.country==="Deutschland")s+=100;if(/Bundesliga|DFB-Pokal|Champions League|Europa League|Conference League|Nations League|Serie A|Premier League|La Liga|Frauen-Bundesliga/i.test(t))s+=80;if(/Deutschland|Bayern|Dortmund|Stuttgart|Leverkusen|Frankfurt|Leipzig|Schalke|Hamburg|Köln|Bremen/i.test(t))s+=60;if(/Saudi|Arabia|Al-Nassr|Al-Hilal/i.test(t))s-=120;return s};
const byDate=dates.map(date=>({date,games:games.filter(g=>g.date===date&&valid(g)&& (mode==="weekend"||isFree(g))).sort((a,b)=>a.time.localeCompare(b.time))}));
if(!byDate.some(d=>d.games.length))throw Error("No verified matches for "+mode+" "+localDate);
const caption=mode==="free-tv"?"Fußball im Free-TV diese Woche":"Fußballhighlights am Wochenende";
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const days=["Sonntag","Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag"];
const label=d=>{const v=new Date(d+"T12:00:00Z");return days[v.getUTCDay()]+", "+d.slice(8,10)+"."+d.slice(5,7)+"."};
const logo="data:image/svg+xml;base64,"+fs.readFileSync("logo.svg").toString("base64");
const css=fs.readFileSync("social/instagram-feed-master.html","utf8").match(/<style>([\s\S]*?)<\/style>/)?.[1]||"";
const extra='.content{justify-content:center}.day-group{break-inside:avoid;page-break-inside:avoid}.day-group+.day-group{margin-top:20px}.date{margin:0 0 18px}.game{padding:13px 0 14px}.game .sender{margin-top:5px}.content h1{margin-bottom:30px}';
const row=g=>'<article class="game"><div class="time">'+esc(g.time)+' Uhr</div><div class="teams">'+esc(g.home)+' – '+esc(g.away)+'</div><div class="sender">'+esc(g.channels.join(" · "))+'</div></article>';
const block=day=>'<section class="day-group"><div class="date">'+esc(label(day.date))+'</div><div class="games">'+day.games.map(row).join("")+'</div></section>';
const daysWithGames=byDate.filter(d=>d.games.length);
const fullHtml=(blocks,heading)=>'<!doctype html><html lang="de"><head><meta charset="utf-8"><link href="https://fonts.googleapis.com/css2?family=Archivo+Black&family=Roboto:wght@400;500;700;900&display=swap" rel="stylesheet"><style>'+css+extra+'</style></head><body><main class="post"><img class="logo" src="'+logo+'"><section class="content">'+(heading?'<h1>'+ (mode==="free-tv"?"FREE-TV-<br>HIGHLIGHTS<br>DIESE WOCHE":"WOCHENEND-<br>HIGHLIGHTS")+'</h1>':"")+blocks.map(block).join("")+'</section><footer class="footer">SPIELTAGAKTUELL.DE</footer></main></body></html>';
fs.mkdirSync("social-output/weekly",{recursive:true});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1080,height:1350},deviceScaleFactor:1});
const fits=async (blocks,heading)=>{await page.setContent(fullHtml(blocks,heading),{waitUntil:"networkidle"});await page.evaluate(()=>document.fonts.ready);return page.evaluate(()=>{let content=document.querySelector(".content"),footer=document.querySelector(".footer"),r=content.getBoundingClientRect();return r.top>=0&&r.bottom<=footer.getBoundingClientRect().top&&content.scrollHeight<=content.clientHeight+1&&[...document.querySelectorAll(".day-group")].every(x=>x.getBoundingClientRect().bottom<=footer.getBoundingClientRect().top-15)});};
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
const coverExt=cover.endsWith(".png")?"png":"jpeg";
const coverPage=await browser.newPage({viewport:{width:1080,height:1350},deviceScaleFactor:1});
await coverPage.setContent('<html><body style="margin:0;position:relative;width:1080px;height:1350px;overflow:hidden"><img style="width:1080px;height:1350px;object-fit:cover" src="data:image/'+coverExt+';base64,'+coverData.toString("base64")+'"><div style="position:absolute;left:303px;top:1204px;width:476px;height:56px;background:#F2AFC0;color:#000;display:flex;align-items:center;justify-content:center;font:700 39px Arial,sans-serif;letter-spacing:1px">'+dateText+'</div></body></html>');
await coverPage.screenshot({path:"social-output/weekly/00.jpg",type:"jpeg",quality:95});
await coverPage.close();
for(let i=0;i<pages.length;i++){await page.setContent(fullHtml(pages[i].days,pages[i].heading),{waitUntil:"networkidle"});await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:"social-output/weekly/"+String(i+1).padStart(2,"0")+".jpg",type:"jpeg",quality:95})}
await browser.close();
const slideFiles=Array.from({length:pages.length+1},(_,i)=>"social-output/weekly/"+String(i).padStart(2,"0")+".jpg");
if(slideFiles.length>10)throw Error("Instagram allows at most 10 carousel items");
const publishedPath="social/published/"+mode+"-"+localDate+".json";
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
for(let i=0;i<slideFiles.length;i++){let url="https://raw.githubusercontent.com/"+process.env.GITHUB_REPOSITORY+"/"+sha+"/social/weekly-generated/"+mode+"-"+localDate+"-"+String(i).padStart(2,"0")+".jpg";let child=await post(api+"/"+id+"/media",{image_url:url,is_carousel_item:"true"});childIds.push(child.id);await wait(child.id)}
const parent=await post(api+"/"+id+"/media",{media_type:"CAROUSEL",children:childIds.join(","),caption:caption+" ("+dates[0].split("-").reverse().join(".")+" – "+dates.at(-1).split("-").reverse().join(".")+")\nAlle Spiele und Sender: spieltagaktuell.de\n\n#fußball #fußballimtv #spieltagaktuell"});
state.container=parent.id;state.children=childIds;save();await wait(parent.id);
state.attempted=true;save();let result=await post(api+"/"+id+"/media_publish",{creation_id:parent.id});state.id=result.id;save();
let confirmation=await get(api+"/"+result.id+"?fields=id,media_type,permalink&access_token="+encodeURIComponent(token));if(confirmation.media_type!=="CAROUSEL")throw Error("Published item is not confirmed carousel");
console.log("Published "+mode+" "+confirmation.permalink);
