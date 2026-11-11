// Session tokens the service issues after Google sign-in: cs1.<payload>.<mac>,
// HMAC-SHA256 over the payload with SESSION_SECRET. Stateless, so a request is
// authenticated without a database read.
const PREFIX = "cs1";
export const SESSION_TTL_S = 30 * 24 * 3600;

const enc = new TextEncoder();
const dec = new TextDecoder();

export function b64urlEncode(bytes) {
  let s = "";
  for (const b of new Uint8Array(bytes)) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function b64urlDecode(str) {
  const bin = atob(str.replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

const hmacKey = (secret, usage) =>
  crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, [usage]);

export async function signSession({ uid, email }, secret, { now = Date.now(), ttl = SESSION_TTL_S } = {}) {
  if (!secret) throw new Error("SESSION_SECRET is not set");
  const payload = b64urlEncode(enc.encode(JSON.stringify({ uid, email, exp: Math.floor(now / 1000) + ttl })));
  const mac = await crypto.subtle.sign("HMAC", await hmacKey(secret, "sign"), enc.encode(`${PREFIX}.${payload}`));
  return `${PREFIX}.${payload}.${b64urlEncode(mac)}`;
}

// Returns { uid, email, exp } or null. Never throws on a malformed token.
export async function verifySession(token, secret, { now = Date.now() } = {}) {
  if (!secret || typeof token !== "string") return null;
  const parts = token.split(".");
  if (parts.length !== 3 || parts[0] !== PREFIX) return null;
  try {
    const ok = await crypto.subtle.verify(
      "HMAC",
      await hmacKey(secret, "verify"),
      b64urlDecode(parts[2]),
      enc.encode(`${PREFIX}.${parts[1]}`)
    );
    if (!ok) return null;
    const p = JSON.parse(dec.decode(b64urlDecode(parts[1])));
    if (typeof p.uid !== "string" || typeof p.exp !== "number" || p.exp * 1000 <= now) return null;
    return p;
  } catch {
    return null;
  }
}
