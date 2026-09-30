import fs from "node:fs";
const games=JSON.parse(fs.readFileSync("games.json","utf8"));
const today=new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Berlin",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
const day=games.filter(g=>g.date===today).sort((a,b)=>a.time.localeCompare(b.time));
if(!day.length){console.log("No games today; nothing to publish.");process.exit(0)}
const uncertain=g=>(g.channels||[]).some(c=>/unbekannt|option/i.test(c));
const score=g=>((g.groups||[]).includes("free")?120:0)+(/Deutschland|Bayern|Bundesliga|Champions League/i.test(g.home+" "+g.away+" "+g.competition)?60:0)+(g.time>="17:00"?15:0);
const highlights=day.filter(g=>!uncertain(g)).sort((a,b)=>score(b)-score(a)||a.time.localeCompare(b.time)).slice(0,4);
fs.mkdirSync("social-output",{recursive:true});
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const logo=Buffer.from(fs.readFileSync("logo.svg","utf8")).toString("base64");
const date=today.split("-").reverse().join(".");
function svg(w,h,story=false){
 const top=story?300:210, titleY=story?500:390, dateY=story?690:550, rowsY=story?830:670, rowH=story?205:145;
 const rows=highlights.map((g,i)=>{const y=rowsY+i*rowH; const teams=esc(g.home+" – "+g.away); const ch=esc(g.channels.join(" · ")); return `<text x="90" y="${y}" font-family="Roboto" font-size="${story?38:30}" font-weight="700">${esc(g.time)} Uhr</text><text x="280" y="${y}" font-family="Archivo Black" font-size="${story?42:34}">${teams}</text><text x="280" y="${y+48}" font-family="Roboto" font-size="${story?30:24}">${ch}</text><line x1="90" y1="${y+82}" x2="${w-90}" y2="${y+82}" stroke="#000" stroke-width="3"/>`;}).join("");
 return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><rect width="100%" height="100%" fill="#F2AFC0"/><image href="data:image/svg+xml;base64,${logo}" x="${(w-380)/2}" y="${story?110:65}" width="380"/><text x="90" y="${titleY}" font-family="Archivo Black" font-size="${story?92:78}"><tspan x="90">FUSSBALL-</tspan><tspan x="90" dy="0.95em">HIGHLIGHTS</tspan><tspan x="90" dy="0.95em">HEUTE</tspan></text><rect x="90" y="${dateY}" width="310" height="74" rx="37" fill="#000"/><text x="245" y="${dateY+51}" text-anchor="middle" font-family="Archivo Black" font-size="34" fill="#F2AFC0">${date}</text>${rows}<text x="${w/2}" y="${h-70}" text-anchor="middle" font-family="Archivo Black" font-size="${story?38:30}">SPIELTAGAKTUELL.DE</text></svg>`;
}
fs.writeFileSync("social-output/feed.svg",svg(1080,1350));
fs.writeFileSync("social-output/story.svg",svg(1080,1920,true));
fs.writeFileSync("social-output/today.json",JSON.stringify({date:today,highlights},null,2));
const free=highlights.some(g=>(g.groups||[]).includes("free"));
const lines=[`Fußball heute im TV & Stream – ${date}`,"",...highlights.map(g=>`${g.time} Uhr: ${g.home} – ${g.away}\nTV/Stream: ${g.channels.join(", ")}`),"", "Alle Spiele, Anstoßzeiten und Sender findest du auf spieltagaktuell.de.","",["#fußballheute","#fußballimtv","#fußballlive",free?"#freetv":null].filter(Boolean).join(" ")];
fs.writeFileSync("social-output/caption.txt",lines.join("\n"));
console.log("Prepared",highlights.length,"highlights for",today);
