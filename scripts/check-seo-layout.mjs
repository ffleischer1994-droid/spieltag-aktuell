import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {chromium} from 'playwright';

const root=process.cwd();
const server=http.createServer((req,res)=>{
 let p=path.join(root,decodeURIComponent(new URL(req.url,'http://localhost').pathname));
 if(fs.existsSync(p)&&fs.statSync(p).isDirectory())p=path.join(p,'index.html');
 if(!p.startsWith(root)||!fs.existsSync(p)){res.writeHead(404);return res.end();}
 res.setHeader('Content-Type',p.endsWith('.svg')?'image/svg+xml':p.endsWith('.json')?'application/json':p.endsWith('.html')?'text/html':'text/plain');
 res.end(fs.readFileSync(p));
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base='http://127.0.0.1:'+server.address().port;
const config=JSON.parse(fs.readFileSync('seo/config.json'));
const registry=JSON.parse(fs.readFileSync('seo/matches.json'));
// Audit every permanent page; sample all priority groups among the much larger, uniform match-page template.
const matches=Object.values(registry).sort((a,b)=>a.path.localeCompare(b.path));
const priority=matches.filter(x=>/Deutschland|U17|Bundesliga|Champions|Frauen/i.test([x.game.home,x.game.away,x.game.competition].join(' ')));
const sample=[...new Map([...priority.slice(0,12),...matches.filter((_,i)=>i%Math.max(1,Math.floor(matches.length/8))===0)].map(x=>[x.path,x])).values()];
const paths=['vereine','sender','ueber','impressum','datenschutz','datenquellen','gaestebuch',...config.map(c=>c.path),...sample.map(x=>x.path)];
const browser=await chromium.launch();
fs.mkdirSync('/tmp/seo-layout',{recursive:true});

try{
 for(const [width,dark] of [[320,false],[390,true],[1440,false]]){
  const context=await browser.newContext({viewport:{width,height:1000}});
  const page=await context.newPage();
  await context.addInitScript(dark=>localStorage.setItem('sa-theme',dark?'dark':'light'),dark);
  for(const p of [...new Set(paths)]){
   await page.goto(base+'/'+p+'/',{waitUntil:'domcontentloaded'});
   await page.evaluate(()=>document.fonts.ready);
   const errors=await page.evaluate(()=>{
    const errors=[];
    if(document.documentElement.scrollWidth>innerWidth)errors.push('Horizontal page overflow');
    if(!document.querySelector('.logo')?.naturalWidth)errors.push('Missing logo');
    if(!document.getElementById('theme-btn'))errors.push('Missing homepage theme toggle');
    if(!document.getElementById('menu-btn'))errors.push('Missing homepage menu button');
    if(!document.getElementById('site-search'))errors.push('Missing homepage search');
    if(!document.querySelector('.site-footer'))errors.push('Missing homepage footer');
    for(const el of document.querySelectorAll('h1,.teams,.badge,.fact strong,.links a,.menu-grid a')){
     const r=el.getBoundingClientRect();
     if(r.left<-1||r.right>innerWidth+1||el.scrollWidth>el.clientWidth+1)errors.push('Overflow '+el.className);
    }
    return errors;
   });
   if(errors.length)throw Error(p+' '+width+': '+errors.join(','));
   if(['fussball-heute','free-tv/diese-woche','verein/fc-bayern-muenchen','sender/zdf','gaestebuch',Object.values(registry)[0]?.path].includes(p)){
    await page.screenshot({path:'/tmp/seo-layout/'+p.replaceAll('/','-')+'-'+width+'.png',fullPage:true});
   }
  }
  console.log('PASS',paths.length,'pages at',width,dark?'dark':'light');
  await context.close();
 }
}finally{
 await browser.close();
 server.close();
}
