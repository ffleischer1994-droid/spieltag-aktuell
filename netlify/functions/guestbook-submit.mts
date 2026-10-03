import { randomUUID } from "node:crypto";
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

const cleanName = (value) =>
  String(value || "")
    .normalize("NFKC")
    .replace(/[\u0000-\u001f\u007f]/g, "")
    .replace(/\s+/g, " ")
    .trim();

const cleanMessage = (value) =>
  String(value || "")
    .normalize("NFKC")
    .replace(/\r\n?/g, "\n")
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "")
    .replace(/\n{4,}/g, "\n\n\n")
    .trim();

function validateStrokes(value) {
  if (!Array.isArray(value)) return [];
  if (value.length > 120) throw new Error("drawing-too-large");

  let totalPoints = 0;
  const cleaned = value.map((stroke) => {
    if (!stroke || ![3, 6, 11].includes(Number(stroke.width)) || !Array.isArray(stroke.points)) {
      throw new Error("invalid-drawing");
    }

    totalPoints += stroke.points.length;
    if (stroke.points.length > 1600 || totalPoints > 12000) {
      throw new Error("drawing-too-large");
    }

    return {
      width: Number(stroke.width),
      points: stroke.points.map((point) => {
        const x = Number(point?.x);
        const y = Number(point?.y);
        if (!Number.isFinite(x) || !Number.isFinite(y) || x < 0 || x > 1 || y < 0 || y > 1) {
          throw new Error("invalid-drawing");
        }
        return {
          x: Math.round(x * 10000) / 10000,
          y: Math.round(y * 10000) / 10000,
        };
      }),
    };
  });

  return cleaned;
}

function basicModeration(name, message) {
  const joined = `${name}\n${message}`;
  const urls = joined.match(/https?:\/\/|www\.|\b[a-z0-9-]+\.(?:com|net|org|de|io|xyz|top)\b/gi) || [];

  if (urls.length > 2) return { allow: false, category: "spam" };
  if (/(.)\1{24,}/u.test(joined)) return { allow: false, category: "spam" };
  if (/\b(?:buy followers|free money|crypto giveaway|casino bonus|telegram me|whatsapp me)\b/i.test(joined)) {
    return { allow: false, category: "spam" };
  }

  return { allow: true, category: "ok" };
}

async function aiModeration({ name, message, drawingPreview }) {
  const baseURL = process.env.OPENAI_BASE_URL;
  const apiKey = process.env.OPENAI_API_KEY;

  if (!baseURL || !apiKey) {
    throw new Error("AI Gateway unavailable");
  }

  const userContent = [
    {
      type: "text",
      text:
        "Nickname: " + name + "\n" +
        "Nachricht: " + message + "\n" +
        (drawingPreview ? "Eine optionale Zeichnung ist angehängt." : "Keine Zeichnung vorhanden."),
    },
  ];

  if (drawingPreview) {
    userContent.push({
      type: "image_url",
      image_url: { url: drawingPreview, detail: "low" },
    });
  }

  const response = await fetch(`${baseURL}/v1/chat/completions`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${apiKey}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: "gpt-4o-mini",
      temperature: 0,
      max_tokens: 120,
      response_format: { type: "json_object" },
      messages: [
        {
          role: "system",
          content:
            'Du moderierst ein öffentliches deutschsprachiges Fußball-Gästebuch. Antworte ausschließlich als JSON: {"allow":true|false,"category":"ok|spam|harassment|hate|sexual|graphic|extremism|personal_data|other"}. Erlaubt sind normale Fußballmeinungen, Rivalität, Kritik, Sarkasmus und gelegentliche milde Kraftausdrücke. Politische Meinungen sind ebenfalls erlaubt. Nicht freigeben: gezielte schwere Beleidigungen/Belästigung, Hass oder abwertende Slurs gegen geschützte Gruppen, Drohungen, explizite Sexualinhalte, drastische Gewalt/Gore, extremistische Propaganda oder eindeutige extremistische Symbole, Doxxing/private Kontaktdaten, Spam/Werbung/Scams oder Anleitungen zu schwerem Fehlverhalten. Prüfe eine angehängte Zeichnung nach denselben Regeln. Im Zweifel bei harmloser Mehrdeutigkeit freigeben.',
        },
        { role: "user", content: userContent },
      ],
    }),
  });

  if (!response.ok) {
    throw new Error(`AI moderation failed: ${response.status}`);
  }

  const data = await response.json();
  const raw = data?.choices?.[0]?.message?.content;
  const verdict = typeof raw === "string" ? JSON.parse(raw) : null;

  if (!verdict || typeof verdict.allow !== "boolean") {
    throw new Error("Invalid moderation response");
  }

  return {
    allow: verdict.allow === true,
    category: String(verdict.category || (verdict.allow ? "ok" : "other")).slice(0, 40),
  };
}

export default async function handler(request) {
  if (request.method !== "POST") {
    return json({ error: "Method not allowed" }, { status: 405 });
  }

  const contentLength = Number(request.headers.get("content-length") || 0);
  if (contentLength > 600_000) {
    return json({ error: "Der Eintrag ist zu groß." }, { status: 413 });
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "Ungültige Anfrage." }, { status: 400 });
  }

  // Honeypot: echte Nutzer sehen dieses Feld nicht.
  if (String(body?.website || "").trim()) {
    return json({ ok: true }, { status: 200 });
  }

  const name = cleanName(body?.name);
  const message = cleanMessage(body?.message);

  if (!name || name.length > 24 || !message || message.length > 500) {
    return json(
      { error: "Bitte Name und Nachricht innerhalb der Zeichenlimits ausfüllen." },
      { status: 400 },
    );
  }

  let strokes;
  try {
    strokes = validateStrokes(body?.strokes);
  } catch {
    return json({ error: "Die Zeichnung ist ungültig oder zu groß." }, { status: 400 });
  }

  let drawingPreview = null;
  if (strokes.length) {
    const preview = String(body?.drawingPreview || "");
    if (
      !/^data:image\/(?:png|jpeg|webp);base64,[a-z0-9+/=]+$/i.test(preview) ||
      preview.length > 350_000
    ) {
      return json({ error: "Die Zeichnung konnte nicht geprüft werden." }, { status: 400 });
    }
    drawingPreview = preview;
  }

  const localVerdict = basicModeration(name, message);
  if (!localVerdict.allow) {
    return json(
      { error: "Dieser Eintrag wurde von der automatischen Moderation nicht freigegeben." },
      { status: 422 },
    );
  }

  let aiVerdict;
  try {
    aiVerdict = await aiModeration({ name, message, drawingPreview });
  } catch (error) {
    console.error("guestbook:moderation", error);
    return json(
      { error: "Die automatische Moderation ist gerade nicht erreichbar. Bitte später erneut versuchen." },
      { status: 503 },
    );
  }

  if (!aiVerdict.allow) {
    return json(
      { error: "Dieser Eintrag wurde von der automatischen Moderation nicht freigegeben." },
      { status: 422 },
    );
  }

  const id = randomUUID();
  const createdAt = new Date().toISOString();
  const entry = { id, name, message, createdAt, strokes };
  const key = `approved/${Date.now().toString().padStart(13, "0")}-${id}`;

  try {
    const store = getStore(STORE_OPTIONS);
    await store.setJSON(
      key,
      {
        ...entry,
        moderation: {
          checkedAt: createdAt,
          model: "gpt-4o-mini",
          category: aiVerdict.category,
        },
      },
      { onlyIfNew: true },
    );
  } catch (error) {
    console.error("guestbook:save", error);
    return json(
      { error: "Der Eintrag konnte gerade nicht gespeichert werden." },
      { status: 500 },
    );
  }

  return json({ ok: true, entry }, { status: 201 });
}

export const config = {
  path: "/api/guestbook/submit",
  method: "POST",
  rateLimit: {
    windowLimit: 3,
    windowSize: 60,
    aggregateBy: ["ip", "domain"],
  },
};
