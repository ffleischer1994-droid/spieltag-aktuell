import fs from "node:fs";
const games=JSON.parse(fs.readFileSync("games.json","utf8"));
const today=new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Berlin",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
const day=games.filter(g=>g.date===today).sort((a,b)=>a.time.localeCompare(b.time));
if(!day.length){console.log("No games today; nothing to publish.");process.exit(1)}
const uncertain=g=>!(g.channels||[]).length||(g.channels||[]).some(c=>/unbekannt|option/i.test(c));
const score=g=>{const teams=g.home+" "+g.away;return (g.country==="Deutschland"?100:0)+(/Bundesliga|2\. Bundesliga|DFB-Pokal|Champions League/i.test(g.competition)?90:0)+(/Deutschland|FC Bayern München|Bayer Leverkusen|Borussia Dortmund|Eintracht Frankfurt|VfB Stuttgart|RB Leipzig|Hamburger SV|FC Schalke 04|1\. FC Köln|Borussia Mönchengladbach|SV Werder Bremen|Hertha BSC/i.test(teams)?60:0)+((g.groups||[]).includes("free")?30:0)+(/Nations League/i.test(g.competition)?20:0)+(g.time>="17:00"?10:0)};
const highlights=day.filter(g=>!uncertain(g)).sort((a,b)=>score(b)-score(a)||a.time.localeCompare(b.time)).slice(0,4).sort((a,b)=>a.time.localeCompare(b.time));
if(!highlights.length) throw new Error("No verified highlights today");
fs.mkdirSync("social-output",{recursive:true});
fs.writeFileSync("social-output/today.json",JSON.stringify({date:today,highlights},null,2));
const date=today.split("-").reverse().join(".");
const free=highlights.some(g=>(g.groups||[]).includes("free"));
const lines=[`Fußball heute im TV & Stream – ${date}`,"",...highlights.map(g=>`${g.time} Uhr: ${g.home} – ${g.away}\nTV/Stream: ${g.channels.join(", ")}`),"","Alle Spiele, Anstoßzeiten und Sender findest du auf spieltagaktuell.de.","",["#fußballheute","#fußballimtv","#fußballlive",free?"#freetv":null].filter(Boolean).join(" ")];
fs.writeFileSync("social-output/caption.txt",lines.join("\n"));
console.log("Prepared",highlights.length,"highlights for",today);

