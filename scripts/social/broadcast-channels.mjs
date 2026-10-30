import fs from "node:fs";
const audio = new RegExp(JSON.parse(fs.readFileSync(new URL("../broadcast-audio.json", import.meta.url), "utf8")).join("|"), "i");
export const isAudioChannel = channel => audio.test(channel);
export const videoOnly = game => ({...game, channels:(game.channels || []).filter(channel => !isAudioChannel(channel))});
export const assertVideoChannels = games => {
  if (games.some(game => !game.channels?.length || game.channels.some(isAudioChannel))) {
    throw new Error("Publish blocked: audio or missing video broadcast in TV/stream list");
  }
};
