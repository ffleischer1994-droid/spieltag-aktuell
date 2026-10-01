import fs from "node:fs";
const token=process.env.IG_ACCESS_TOKEN;
if(!token){console.error("IG_ACCESS_TOKEN missing");process.exit(1)}
if(!fs.existsSync("social-output/today.json")){console.log("No social package today.");process.exit(0)}
const caption=fs.readFileSync("social-output/caption.txt","utf8");
const base="https://raw.githubusercontent.com/ffleischer1994-droid/spieltag-aktuell/main/social/";
const feedUrl=base+"latest-feed.png?ts="+Date.now(), storyUrl=base+"latest-story.png?ts="+Date.now();
const get=async u=>{const r=await fetch(u);if(!r.ok)throw new Error(await r.text());return r.json()};
const post=async(u,data)=>{const r=await fetch(u,{method:"POST",headers:{"content-type":"application/x-www-form-urlencoded"},body:new URLSearchParams({...data,access_token:token})});if(!r.ok)throw new Error(await r.text());return r.json()};
let host,id;
try{
 const me=await get("https://graph.instagram.com/me?fields=user_id,username&access_token="+encodeURIComponent(token));
 id=me.user_id||me.id; host="https://graph.instagram.com";
 console.log("Using Instagram Login account",me.username||id);
}catch{
 const pages=await get("https://graph.facebook.com/me/accounts?fields=instagram_business_account{id,username}&access_token="+encodeURIComponent(token));
 const page=(pages.data||[]).find(x=>x.instagram_business_account);
 if(!page)throw new Error("No Instagram professional account found for this token.");
 id=page.instagram_business_account.id; host="https://graph.facebook.com";
 console.log("Using Facebook Login Instagram account",page.instagram_business_account.username||id);
}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function publish(data){
 const c=await post(host+"/"+id+"/media",data);
 for(let i=0;i<12;i++){
   await sleep(i===0?5000:3000);
   const s=await get(host+"/"+c.id+"?fields=status_code,status&access_token="+encodeURIComponent(token));
   console.log("Media container",c.id,"status:",s.status_code||s.status||"unknown");
   if(s.status_code==="FINISHED"){
     const result=await post(host+"/"+id+"/media_publish",{creation_id:c.id});
     return result.id;
   }
   if(s.status_code==="ERROR"||s.status_code==="EXPIRED") throw new Error("Instagram media container failed: "+JSON.stringify(s));
 }
 throw new Error("Instagram media container was not ready after waiting.");
}
async function verifyPublished(mediaId,expectedType,label){
  let last=null;
  for(let i=0;i<10;i++){
    await sleep(i===0?3000:2000);
    try{
      last=await get(host+"/"+mediaId+"?fields=id,media_type,permalink,timestamp&access_token="+encodeURIComponent(token));
      if(last?.id&&(!expectedType||last.media_type===expectedType)){
        console.log(label+" verified:",last.id,last.media_type,last.permalink||"");
        return last;
      }
    }catch(e){last={error:String(e)}}
  }
  throw new Error(label+" was accepted by media_publish but could not be verified as published: "+JSON.stringify(last));
}
const feed=await publish({image_url:feedUrl,caption});
await verifyPublished(feed,"IMAGE","Feed");
const story=await publish({media_type:"STORIES",image_url:storyUrl});
await verifyPublished(story,"STORY","Story");
console.log("Instagram publish verified: feed + story");
