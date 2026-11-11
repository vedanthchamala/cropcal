// Google sign-in for the CropCal service. Thin wrapper over chrome.identity and
// chrome.storage; the testable parts live in auth-url.js.
import { GOOGLE_CLIENT_ID, buildAuthUrl, parseAuthRedirect } from "./auth-url.js";

export const signInConfigured = () => Boolean(GOOGLE_CLIENT_ID);

function randomNonce() {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");
}

// interactive:false renews silently when Google still has a session for the
// account, and fails otherwise instead of opening a window.
export async function signIn(serviceUrl, { interactive = true, loginHint = "" } = {}) {
  if (!signInConfigured()) throw new Error("Sign-in is not set up in this build");
  const nonce = randomNonce();
  const url = buildAuthUrl({
    clientId: GOOGLE_CLIENT_ID,
    redirectUri: chrome.identity.getRedirectURL(),
    nonce,
    interactive,
    loginHint
  });
  let redirect;
  try {
    redirect = await chrome.identity.launchWebAuthFlow({ url, interactive });
  } catch (err) {
    throw new Error(interactive ? `Google sign-in was cancelled (${err.message})` : "Sign in to CropCal again");
  }
  const idToken = parseAuthRedirect(redirect, nonce);

  let res;
  try {
    res = await fetch(`${serviceUrl}/auth/google`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_token: idToken })
    });
  } catch (err) {
    throw new Error(`Cannot reach the CropCal service (${err.message})`);
  }
  const data = await res.json().catch(() => null);
  if (!res.ok || !data?.token) throw new Error(data?.error || `Sign-in failed (HTTP ${res.status})`);
  await chrome.storage.local.set({ sessionToken: data.token, email: data.email });
  return { sessionToken: data.token, email: data.email, limit: data.limit };
}

export async function signOut() {
  await chrome.storage.local.remove(["sessionToken", "email"]);
}
