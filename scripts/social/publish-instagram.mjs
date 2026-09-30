import fs from "node:fs";
const token=process.env.IG_ACCESS_TOKEN;
if(!token){console.error("IG_ACCESS_TOKEN missing");process.exit(1)}
if(!fs.existsSync("social-output/today.json")){console.log("No social package today.");process.exit(0)}
const caption=fs.readFileSync("social-output/caption.txt","utf8");
const base="https://raw.githubusercontent.com/ffleischer1994-droid/spieltag-aktuell/main/social/";
const feedUrl=base+"latest-feed.jpg?ts="+Date.now(), storyUrl=base+"latest-story.jpg?ts="+Date.now();
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
async function publish(data){
 const c=await post(host+"/"+id+"/media",data);
 const result=await post(host+"/"+id+"/media_publish",{creation_id:c.id});
 return result.id;
}
const feed=await publish({image_url:feedUrl,caption});
console.log("Feed published:",feed);
const story=await publish({media_type:"STORIES",image_url:storyUrl});
console.log("Story published:",story);
