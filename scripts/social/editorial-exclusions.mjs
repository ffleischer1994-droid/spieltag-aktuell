// Permanent editorial exclusion requested by the owner: no Icon League in social posts.
export const excludedFromSocial = game =>
  /\bicon[\s_-]*league\b/i.test(
    [game.competition, game.league, game.tournament, ...(game.channels || [])].filter(Boolean).join(" ")
  );
