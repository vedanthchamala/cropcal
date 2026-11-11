import test from "node:test";
import assert from "node:assert/strict";
import { buildAuthUrl, parseAuthRedirect } from "../extension/lib/auth-url.js";

const REDIRECT = "https://abcdefghijklmnopabcdefghijklmnop.chromiumapp.org/";
const jwt = (claims) => `h.${Buffer.from(JSON.stringify(claims)).toString("base64url")}.s`;

test("auth URL asks Google for an ID token only, with the nonce and redirect", () => {
  const u = new URL(buildAuthUrl({ clientId: "cid", redirectUri: REDIRECT, nonce: "n1" }));
  assert.equal(u.origin + u.pathname, "https://accounts.google.com/o/oauth2/v2/auth");
  assert.equal(u.searchParams.get("response_type"), "id_token");
  assert.equal(u.searchParams.get("scope"), "openid email");
  assert.equal(u.searchParams.get("client_id"), "cid");
  assert.equal(u.searchParams.get("redirect_uri"), REDIRECT);
  assert.equal(u.searchParams.get("nonce"), "n1");
  assert.equal(u.searchParams.get("prompt"), "select_account");
  assert.equal(u.searchParams.has("login_hint"), false);

  const silent = new URL(buildAuthUrl({ clientId: "cid", redirectUri: REDIRECT, nonce: "n", interactive: false, loginHint: "a@b.c" }));
  assert.equal(silent.searchParams.get("prompt"), "none");
  assert.equal(silent.searchParams.get("login_hint"), "a@b.c");
});

test("redirect parsing returns the ID token only when the nonce matches", () => {
  const token = jwt({ sub: "1", nonce: "n1" });
  assert.equal(parseAuthRedirect(`${REDIRECT}#id_token=${token}&authuser=0`, "n1"), token);
  assert.throws(() => parseAuthRedirect(`${REDIRECT}#id_token=${token}`, "other"), /did not match/);
  assert.throws(() => parseAuthRedirect(`${REDIRECT}#id_token=${token}`, ""), /did not match/);
  assert.throws(() => parseAuthRedirect(`${REDIRECT}#id_token=${jwt({ sub: "1" })}`, "n1"), /did not match/);
  assert.throws(() => parseAuthRedirect(`${REDIRECT}#error=access_denied`, "n1"), /access_denied/);
  assert.throws(() => parseAuthRedirect(`${REDIRECT}#state=x`, "n1"), /no token/);
  assert.throws(() => parseAuthRedirect(`${REDIRECT}#id_token=garbage`, "n1"), /unreadable/);
});
