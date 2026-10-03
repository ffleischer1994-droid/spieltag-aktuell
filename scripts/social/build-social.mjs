import fs from "node:fs";

const games=JSON.parse(fs.readFileSync("games.json","utf8"));
const today=new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Berlin",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
const day=games.filter(g=>g.date===today).sort((a,b)=>a.time.localeCompare(b.time));
if(!day.length){console.log("No games today; nothing to publish.");process.exit(1)}

const uncertain=g=>!(g.channels||[]).length||(g.channels||[]).some(c=>/unbekannt|option/i.test(c));
const sourceConfidence=g=>g.verifiedAt?45:((g.sources||[]).length?25:0);

const score=g=>{
  const teams=g.home+" "+g.away;
  const competition=g.competition||"";
  let value=sourceConfidence(g);
  if(g.country==="Deutschland")value+=120;
  if(/Bundesliga|2\. Bundesliga|DFB-Pokal|Champions League|Europa League|Conference League/i.test(competition))value+=95;
  if(/Frauen-Bundesliga/i.test(competition))value+=95;
  if(/Deutschland|FC Bayern München|Bayer(?: 04)? Leverkusen|Borussia Dortmund|Eintracht Frankfurt|VfB Stuttgart|RB Leipzig|Hamburger SV|FC Schalke 04|1\. FC Köln|Borussia Mönchengladbach|SV Werder Bremen|VfL Wolfsburg/i.test(teams))value+=75;
  if(/Deutschland/i.test(teams))value+=35;
  if((g.groups||[]).includes("free"))value+=20;
  if(/Nations League/i.test(competition))value+=15;
  if(g.time>="17:00")value+=10;
  return value;
};

const candidates=day.filter(g=>!uncertain(g)).map(g=>({...g,_score:score(g)}));
const highlights=candidates
  .sort((a,b)=>b._score-a._score||a.time.localeCompare(b.time))
  .slice(0,4)
  .sort((a,b)=>a.time.localeCompare(b.time))
  .map(({_score,...g})=>g);

if(!highlights.length)throw new Error("No verified highlights today");

fs.mkdirSync("social-output",{recursive:true});
fs.writeFileSync("social-output/today.json",JSON.stringify({date:today,highlights},null,2));
fs.writeFileSync("social-output/selection.json",JSON.stringify({
  date:today,
  candidates:candidates
    .sort((a,b)=>b._score-a._score||a.time.localeCompare(b.time))
    .map(g=>({time:g.time,home:g.home,away:g.away,competition:g.competition,score:g._score,sourceBacked:Boolean(g.verifiedAt||(g.sources||[]).length)})),
  selected:highlights.map(g=>g.time+" "+g.home+" – "+g.away)
},null,2));

const date=today.split("-").reverse().join(".");
const free=highlights.some(g=>(g.groups||[]).includes("free"));
const lines=[
  `Fußball heute im TV & Stream – ${date}`,
  "",
  ...highlights.map(g=>`${g.time} Uhr: ${g.home} – ${g.away}\nTV/Stream: ${g.channels.join(", ")}`),
  "",
  "Alle Spiele, Anstoßzeiten und Sender findest du auf spieltagaktuell.de.",
  "",
  ["#fußballheute","#fußballimtv","#fußballlive",free?"#freetv":null].filter(Boolean).join(" ")
];
fs.writeFileSync("social-output/caption.txt",lines.join("\n"));
console.log("Prepared",highlights.length,"highlights for",today);
