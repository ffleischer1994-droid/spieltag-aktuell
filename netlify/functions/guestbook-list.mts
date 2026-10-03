import { getStore } from "@netlify/blobs";

const STORE_OPTIONS = {
  name: "spieltag-guestbook",
  region: "eu-central-1",
  consistency: "strong",
};

const json = (data, init = {}) =>
  Response.json(data, {
    ...init,
    headers: {
      "cache-control": "no-store, max-age=0",
      ...(init.headers || {}),
    },
  });

export default async function handler(request) {
  if (request.method !== "GET") {
    return json({ error: "Method not allowed" }, { status: 405 });
  }

  try {
    const store = getStore(STORE_OPTIONS);
    const { blobs } = await store.list({ prefix: "approved/" });

    const keys = blobs
      .map((blob) => blob.key)
      .sort((a, b) => b.localeCompare(a));

    const entries = (
      await Promise.all(
        keys.map((key) =>
          store.get(key, { type: "json", consistency: "strong" }).catch(() => null),
        ),
      )
    )
      .filter(Boolean)
      .sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)))
      .map(({ id, name, message, createdAt, strokes }) => ({
        id,
        name,
        message,
        createdAt,
        strokes: Array.isArray(strokes) ? strokes : [],
      }));

    return json({ entries });
  } catch (error) {
    console.error("guestbook:list", error);
    return json(
      { error: "Gästebucheinträge konnten gerade nicht geladen werden." },
      { status: 500 },
    );
  }
}

export const config = {
  path: "/api/guestbook",
  method: "GET",
};
