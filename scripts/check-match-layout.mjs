import fs from 'node:fs';
import {chromium} from 'playwright';
const browser=await chromium.launch();
fs.mkdirSync('layout-output',{recursive:true});
const html=fs.readFileSync('index.html','utf8');
for(const width of [320,375,560,850,851,1024,1440]){
 for(const dark of width>850?[false,true]:[false]){
 const page=await browser.newPage({viewport:{width,height:1000}});
 await page.route('https://layout.test/**',route=>route.fulfill({contentType:'text/html',body:html}));
 await page.goto('https://layout.test/');
 await page.evaluate((dark)=>{
 document.body.classList.toggle('dark-mode',dark);
 const g={date:'2026-10-01',time:'20:45',home:'Frankreich',away:'Italien',competition:'Nations League',country:'Europa',channels:['DAZN 1','RSI LA 2 (CH)','RTS 2 (CH)','SRF zwei (CH)','DAZN','Play RSI (CH)','Play SRF','Play SRF (App)','SRF Sport (CH)'],groups:['dazn','other']};
 document.getElementById('game-list').innerHTML='<div class="time-block"><div class="matches">'+match(g)+match({...g,home:'Borussia Mönchengladbach Frauen',away:'SpVgg Greuther Fürth Nachwuchsmannschaft',channels:[...g.channels,'SehrLangerSendernameOhneLeerzeichen'.repeat(3)]})+'</div></div>';
 },dark);
 await page.evaluate(()=>document.fonts.ready);
 const errors=await page.evaluate(()=>{
 const errors=[];
 for(const row of document.querySelectorAll('.match')){
 const box=row.getBoundingClientRect();
 for(const el of row.querySelectorAll('.time,.teams,.meta,.match-actions button,.badge')){
 const r=el.getBoundingClientRect();
 if(r.left<box.left||r.right>box.right+1||el.scrollWidth>el.clientWidth+1)errors.push('Overflow '+el.className);
 }
 const [time,copy,providers]=[...row.children].map(el=>el.getBoundingClientRect());
 if(time.right>copy.left)errors.push('Time overlaps teams');
 if(providers.left<copy.right&&providers.top<copy.bottom&&providers.bottom>copy.top)errors.push('Providers overlap teams');
 }
 return errors;
 });
 if(errors.length)throw Error(width+' '+dark+': '+errors.join(','));
 await page.screenshot({path:'layout-output/'+width+'-'+dark+'.png',fullPage:true});
 await page.close();
 console.log('PASS',width,dark?'dark':'light');
 }
}
await browser.close();
