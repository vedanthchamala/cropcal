// Verifies a Google ID token the way Google documents for backends: RS256
// signature against Google's published keys, then iss / aud / exp. The `aud`
// check is what stops a token issued to some other app being replayed here.
import { b64urlDecode } from "./session.js";

export const GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs";
const ISSUERS = new Set(["https://accounts.google.com", "accounts.google.com"]);
const JWKS_TTL_MS = 3600_000;
const CLOCK_SKEW_S = 60;

let cache = { keys: [], at: 0 };

async function googleKeys(fetchImpl, now, force) {
  if (!force && cache.keys.length && now - cache.at < JWKS_TTL_MS) return cache.keys;
  const res = await fetchImpl(GOOGLE_JWKS_URL);
  if (!res.ok) throw new Error("Could not load Google's signing keys");
  cache = { keys: (await res.json()).keys || [], at: now };
  return cache.keys;
}

export function resetGoogleKeyCache() {
  cache = { keys: [], at: 0 };
}

const json = (part) => JSON.parse(new TextDecoder().decode(b64urlDecode(part)));

// Returns { sub, email } or throws an Error whose message is safe to show.
export async function verifyGoogleIdToken(idToken, { clientId, fetchImpl = fetch, now = Date.now() }) {
  if (!clientId) throw new Error("Sign-in is not configured");
  const parts = typeof idToken === "string" ? idToken.split(".") : [];
  if (parts.length !== 3) throw new Error("Invalid Google sign-in token");
  let header, claims;
  try {
    header = json(parts[0]);
    claims = json(parts[1]);
  } catch {
    throw new Error("Invalid Google sign-in token");
  }
  if (header.alg !== "RS256" || !header.kid) throw new Error("Invalid Google sign-in token");

  let jwk = (await googleKeys(fetchImpl, now, false)).find((k) => k.kid === header.kid);
  if (!jwk) jwk = (await googleKeys(fetchImpl, now, true)).find((k) => k.kid === header.kid);
  if (!jwk) throw new Error("Invalid Google sign-in token");

  const key = await crypto.subtle.importKey(
    "jwk",
    { kty: jwk.kty, n: jwk.n, e: jwk.e, alg: "RS256", ext: true },
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"]
  );
  const signed = new TextEncoder().encode(`${parts[0]}.${parts[1]}`);
  const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, b64urlDecode(parts[2]), signed);
  if (!ok) throw new Error("Invalid Google sign-in token");

  const nowS = Math.floor(now / 1000);
  if (!ISSUERS.has(claims.iss)) throw new Error("Invalid Google sign-in token");
  if (claims.aud !== clientId) throw new Error("This sign-in was issued for a different app");
  if (typeof claims.exp !== "number" || claims.exp + CLOCK_SKEW_S < nowS) throw new Error("Google sign-in expired — try again");
  if (!claims.sub) throw new Error("Invalid Google sign-in token");
  if (!claims.email || claims.email_verified !== true) throw new Error("Your Google account's email is not verified");
  return { sub: String(claims.sub), email: String(claims.email).toLowerCase() };
}
