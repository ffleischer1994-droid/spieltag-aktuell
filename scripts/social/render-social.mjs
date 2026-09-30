import sharp from "sharp";
import fs from "node:fs";
if(!fs.existsSync("social-output/today.json")) process.exit(0);
const data=JSON.parse(fs.readFileSync("social-output/today.json","utf8"));
const date=data.date, highlights=data.highlights, pink="#F2AFC0";
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const logo=Buffer.from(fs.readFileSync("logo.svg","utf8")).toString("base64");
const pretty=date.split("-").reverse().join(".");
function fit(text,max){return Math.max(24,Math.min(max,Math.floor(max*36/Math.max(36,String(text).length))))}
function make(w,h,story){
 const logoY=story?115:70, titleY=story?470:335, titleSize=story?86:72, gap=story?82:68;
 const pillY=story?690:530, rowsStart=story?865:690, rowH=story?205:135, teamX=story?300:260;
 const rows=highlights.map((g,i)=>{
  const y=rowsStart+i*rowH, ts=fit(g.home+" – "+g.away,story?39:34);
  return '<text x="90" y="'+y+'" font-family="Roboto" font-size="'+(story?34:28)+'" font-weight="700">'+esc(g.time)+' Uhr</text>'+
  '<text x="'+teamX+'" y="'+y+'" font-family="Archivo Black" font-size="'+ts+'">'+esc(g.home+" – "+g.away)+'</text>'+
  '<text x="'+teamX+'" y="'+(y+44)+'" font-family="Roboto" font-size="'+(story?27:23)+'">'+esc(g.channels.join(" · "))+'</text>'+
  '<line x1="90" y1="'+(y+78)+'" x2="'+(w-90)+'" y2="'+(y+78)+'" stroke="#000" stroke-width="2"/>';
 }).join("");
 return '<svg xmlns="http://www.w3.org/2000/svg" width="'+w+'" height="'+h+'" viewBox="0 0 '+w+' '+h+'">'+
 '<rect width="'+w+'" height="'+h+'" fill="'+pink+'"/>'+
 '<image href="data:image/svg+xml;base64,'+logo+'" x="'+((w-380)/2)+'" y="'+logoY+'" width="380"/>'+
 '<text x="90" y="'+titleY+'" font-family="Archivo Black" font-size="'+titleSize+'"><tspan x="90">FUSSBALL-</tspan><tspan x="90" dy="'+gap+'">HIGHLIGHTS</tspan><tspan x="90" dy="'+gap+'">HEUTE</tspan></text>'+
 '<rect x="90" y="'+pillY+'" width="315" height="72" rx="36" fill="#000"/>'+
 '<text x="247.5" y="'+(pillY+49)+'" text-anchor="middle" font-family="Archivo Black" font-size="32" fill="'+pink+'">'+pretty+'</text>'+
 rows+'<text x="'+(w/2)+'" y="'+(h-65)+'" text-anchor="middle" font-family="Archivo Black" font-size="'+(story?36:29)+'">SPIELTAGAKTUELL.DE</text></svg>';
}
for(const item of [["feed",1080,1350,false],["story",1080,1920,true]]){
 const name=item[0],svg=make(item[1],item[2],item[3]);
 fs.writeFileSync("social-output/"+name+".svg",svg);
 await sharp(Buffer.from(svg)).jpeg({quality:95,chromaSubsampling:"4:4:4"}).toFile("social-output/"+name+".jpg");
}
console.log("Rendered approved feed and story layouts");
