// Pure helpers for Google sign-in through chrome.identity.launchWebAuthFlow.
// The flow asks Google for an ID token only (scopes: openid email); the CropCal
// service verifies it and answers with its own session token.

// OAuth client of type "Web application" whose authorised redirect URI is
// https://<extension id>.chromiumapp.org/ . Empty until the store ID exists.
export const GOOGLE_CLIENT_ID = "";

const AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth";

export function buildAuthUrl({ clientId, redirectUri, nonce, interactive = true, loginHint = "" }) {
  const p = new URLSearchParams({
    client_id: clientId,
    response_type: "id_token",
    redirect_uri: redirectUri,
    scope: "openid email",
    nonce,
    prompt: interactive ? "select_account" : "none"
  });
  if (loginHint) p.set("login_hint", loginHint);
  return `${AUTH_ENDPOINT}?${p}`;
}

function decodePayload(jwt) {
  const part = jwt.split(".")[1] || "";
  const b64 = part.replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))));
}

// Pulls the ID token out of the redirect URL's fragment and checks it answers
// THIS sign-in attempt (nonce). The signature is verified by the service.
export function parseAuthRedirect(redirectUrl, expectedNonce) {
  const hash = new URL(redirectUrl).hash.replace(/^#/, "");
  const p = new URLSearchParams(hash);
  if (p.get("error")) throw new Error(`Google sign-in failed (${p.get("error")})`);
  const idToken = p.get("id_token");
  if (!idToken) throw new Error("Google sign-in returned no token");
  let claims;
  try {
    claims = decodePayload(idToken);
  } catch {
    throw new Error("Google sign-in returned an unreadable token");
  }
  if (!expectedNonce || claims.nonce !== expectedNonce) throw new Error("Google sign-in response did not match this request");
  return idToken;
}
