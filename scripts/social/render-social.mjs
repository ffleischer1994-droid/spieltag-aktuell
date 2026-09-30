import sharp from "sharp";
import fs from "node:fs";
if(!fs.existsSync("social-output/feed.svg")) process.exit(0);
await sharp("social-output/feed.svg").jpeg({quality:94,chromaSubsampling:"4:4:4"}).toFile("social-output/feed.jpg");
await sharp("social-output/story.svg").jpeg({quality:94,chromaSubsampling:"4:4:4"}).toFile("social-output/story.jpg");
console.log("Rendered feed.jpg and story.jpg");
