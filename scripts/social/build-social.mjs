import fs from "node:fs";
const games=JSON.parse(fs.readFileSync("games.json","utf8"));
const now=new Date();
const today=new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Berlin",year:"numeric",month:"2-digit",day:"2-digit"}).format(now);
const day=games.filter(g=>g.date===today).sort((a,b)=>a.time.localeCompare(b.time));
if(!day.length){console.log("No games today; nothing to publish.");process.exit(0)}
// Keep selection deterministic: verified data from games.json, earliest/high-signal games first.
// Visual renderer will use the approved Spieltag Aktuell layout.
const score=g=>((g.groups||[]).includes("free")?100:0)+(/Deutschland|Bundesliga|Champions|Europa|Conference|Nations/i.test(g.home+" "+g.away+" "+g.competition)?40:0);
const highlights=[...day].sort((a,b)=>score(b)-score(a)||a.time.localeCompare(b.time)).slice(0,4);
fs.mkdirSync("social-output",{recursive:true});
fs.writeFileSync("social-output/today.json",JSON.stringify({date:today,highlights},null,2));
const keywords=["Fußball heute","Fußball im TV","Fußball live","TV und Stream",...new Set(highlights.flatMap(g=>[g.home,g.away,g.competition]))];
const lines=[`Fußball heute im TV & Stream – ${today.split("-").reverse().join(".")}`,"",...highlights.map(g=>`${g.time} Uhr: ${g.home} – ${g.away}\nTV/Stream: ${g.channels.join(", ")}`),"", "Alle Spiele, Anstoßzeiten und Sender: spieltagaktuell.de","", "#fußballheute #fußballimtv #fußballlive #freetv"];
fs.writeFileSync("social-output/caption.txt",lines.join("\n"));
console.log("Prepared",highlights.length,"highlights. Keywords:",keywords.join(", "));
