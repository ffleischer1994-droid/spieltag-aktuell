import fs from 'node:fs';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';
const statePath='social/auth/instagram-token.enc.json';
const seed=()=>{const v=process.env.IG_ACCESS_TOKEN;if(!v)throw new Error('IG_ACCESS_TOKEN missing');return v;};
const fingerprint=v=>crypto.createHash('sha256').update(v).digest('hex');
const key=v=>crypto.hkdfSync('sha256',v,'spieltag-aktuell','instagram-token-state-v1',32);
export function seal(data,secret){
 const iv=crypto.randomBytes(12), cipher=crypto.createCipheriv('aes-256-gcm',key(secret),iv);
 const body=Buffer.concat([cipher.update(JSON.stringify(data),'utf8'),cipher.final()]);
 return {version:1,seed:fingerprint(secret),iv:iv.toString('base64'),tag:cipher.getAuthTag().toString('base64'),body:body.toString('base64')};
}
export function unseal(data,secret){
 const cipher=crypto.createDecipheriv('aes-256-gcm',key(secret),Buffer.from(data.iv,'base64'));
 cipher.setAuthTag(Buffer.from(data.tag,'base64'));
 return JSON.parse(Buffer.concat([cipher.update(Buffer.from(data.body,'base64')),cipher.final()]).toString('utf8'));
}
function read(){
 const secret=seed();
 if(fs.existsSync(statePath)){
  const envelope=JSON.parse(fs.readFileSync(statePath,'utf8'));
  if(envelope.seed===fingerprint(secret))return unseal(envelope,secret);
 }
 return {token:secret,refreshedAt:Date.now()};
}
export function activeToken(){return read().token;}
export async function maintainToken(){
 let state=read();
 const secret=seed();
 const initialized=fs.existsSync(statePath)&&JSON.parse(fs.readFileSync(statePath,'utf8')).seed===fingerprint(secret);
 if(initialized&&Date.now()-state.refreshedAt<7*86400000)return;
 if(!initialized){
  fs.mkdirSync('social/auth',{recursive:true});
  fs.writeFileSync(statePath,JSON.stringify(seal(state,secret),null,2));
  console.log('Token renewal initialized; first renewal after seven days.');
  return;
 }
 const url=new URL('https://graph.instagram.com/refresh_access_token');
 url.searchParams.set('grant_type','ig_refresh_token');
 url.searchParams.set('access_token',state.token);
 let result;
 try{
  const response=await fetch(url,{signal:AbortSignal.timeout(30000)});
  result=await response.json();
  if(!response.ok||!result.access_token||!(result.expires_in>86400))throw new Error('refresh rejected');
 }catch{
  console.log('::warning::Instagram token renewal failed; will retry next run.');
  if(Date.now()-state.refreshedAt>45*86400000)throw new Error('Token renewal overdue; Instagram authorization must be checked.');
  return;
 }
 state={token:result.access_token,refreshedAt:Date.now(),expiresAt:Date.now()+result.expires_in*1000};
 fs.writeFileSync(statePath,JSON.stringify(seal(state,secret),null,2));
 console.log('Instagram token renewed; encrypted state saved.');
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)await maintainToken();
