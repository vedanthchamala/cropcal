import test from "node:test";
import assert from "node:assert/strict";
import { GOOGLE_JWKS_URL, resetGoogleKeyCache, verifyGoogleIdToken } from "../proxy/src/google.js";
import { makeIssuer } from "./helpers/google-token.js";

const CLIENT = "123-abc.apps.googleusercontent.com";
const NOW = Date.parse("2026-11-11T12:00:00Z");
const base = {
  iss: "https://accounts.google.com", aud: CLIENT, sub: "1098765", email: "Person@Example.com",
  email_verified: true, exp: NOW / 1000 + 3600
};

function jwksFetch(jwks) {
  const calls = [];
  const fetchImpl = async (url) => {
    calls.push(String(url));
    return { ok: true, json: async () => jwks };
  };
  return { fetchImpl, calls };
}

test("a valid Google ID token yields sub and a lower-cased email", async () => {
  resetGoogleKeyCache();
  const issuer = await makeIssuer();
  const { fetchImpl, calls } = jwksFetch(issuer.jwks);
  const out = await verifyGoogleIdToken(await issuer.idToken(base), { clientId: CLIENT, fetchImpl, now: NOW });
  assert.deepEqual(out, { sub: "1098765", email: "person@example.com" });
  assert.deepEqual(calls, [GOOGLE_JWKS_URL]);
  await verifyGoogleIdToken(await issuer.idToken(base), { clientId: CLIENT, fetchImpl, now: NOW });
  assert.equal(calls.length, 1, "keys are cached");
});

test("wrong audience, issuer, expiry, unverified email and bad signatures are rejected", async () => {
  resetGoogleKeyCache();
  const issuer = await makeIssuer();
  const other = await makeIssuer();
  const { fetchImpl } = jwksFetch(issuer.jwks);
  const check = async (claims, re, opts) =>
    assert.rejects(
      async () => verifyGoogleIdToken(await (opts?.by || issuer).idToken(claims, opts), { clientId: CLIENT, fetchImpl, now: NOW }),
      re
    );
  await check({ ...base, aud: "someone-else.apps.googleusercontent.com" }, /different app/);
  await check({ ...base, iss: "https://evil.example" }, /Invalid/);
  await check({ ...base, exp: NOW / 1000 - 600 }, /expired/);
  await check({ ...base, email_verified: false }, /not verified/);
  await check({ ...base, email: undefined }, /not verified/);
  await check({ ...base, sub: undefined }, /Invalid/);
  await check(base, /Invalid/, { by: other });
  await check(base, /Invalid/, { headerKid: "unknown-kid" });
  await check(base, /Invalid/, { alg: "none" });

  const [h, , s] = (await issuer.idToken(base)).split(".");
  const swapped = Buffer.from(JSON.stringify({ ...base, sub: "attacker" })).toString("base64url");
  await assert.rejects(() => verifyGoogleIdToken(`${h}.${swapped}.${s}`, { clientId: CLIENT, fetchImpl, now: NOW }), /Invalid/);
  for (const bad of ["", "a.b", "a.b.c", null]) {
    await assert.rejects(() => verifyGoogleIdToken(bad, { clientId: CLIENT, fetchImpl, now: NOW }), /Invalid/);
  }
  await assert.rejects(async () => verifyGoogleIdToken(await issuer.idToken(base), { clientId: "", fetchImpl, now: NOW }), /not configured/);
});

test("an unknown key id triggers one refetch, so Google's key rotation is picked up", async () => {
  resetGoogleKeyCache();
  const old = await makeIssuer("old");
  const rotated = await makeIssuer("new");
  let served = old.jwks;
  let n = 0;
  const fetchImpl = async () => (n++, { ok: true, json: async () => served });
  await verifyGoogleIdToken(await old.idToken(base), { clientId: CLIENT, fetchImpl, now: NOW });
  served = rotated.jwks;
  await verifyGoogleIdToken(await rotated.idToken(base), { clientId: CLIENT, fetchImpl, now: NOW });
  assert.equal(n, 2);
});
