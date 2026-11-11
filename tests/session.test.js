import test from "node:test";
import assert from "node:assert/strict";
import { SESSION_TTL_S, signSession, verifySession } from "../proxy/src/session.js";

const SECRET = "test-secret-0123456789";
const NOW = Date.parse("2026-11-11T12:00:00Z");

test("a signed session verifies and carries uid, email and a 30-day expiry", async () => {
  const token = await signSession({ uid: "u-1", email: "a@example.com" }, SECRET, { now: NOW });
  assert.match(token, /^cs1\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/);
  const s = await verifySession(token, SECRET, { now: NOW + 1000 });
  assert.deepEqual(s, { uid: "u-1", email: "a@example.com", exp: NOW / 1000 + SESSION_TTL_S });
});

test("expired, tampered, wrong-secret and malformed tokens are rejected without throwing", async () => {
  const token = await signSession({ uid: "u-1", email: "a@example.com" }, SECRET, { now: NOW });
  assert.equal(await verifySession(token, SECRET, { now: NOW + SESSION_TTL_S * 1000 }), null);
  assert.equal(await verifySession(token, "other-secret", { now: NOW }), null);

  const [p, payload, mac] = token.split(".");
  const forged = Buffer.from(JSON.stringify({ uid: "u-2", email: "a@example.com", exp: 9e9 })).toString("base64url");
  assert.equal(await verifySession(`${p}.${forged}.${mac}`, SECRET, { now: NOW }), null);
  assert.equal(await verifySession(`${p}.${payload}.AAAA`, SECRET, { now: NOW }), null);
  assert.equal(await verifySession(`cs2.${payload}.${mac}`, SECRET, { now: NOW }), null);

  for (const bad of ["", "cs1", "cs1..", "a.b.c", "cs1.%%%.%%%", null, undefined, 42]) {
    assert.equal(await verifySession(bad, SECRET, { now: NOW }), null);
  }
  assert.equal(await verifySession(token, "", { now: NOW }), null);
  await assert.rejects(() => signSession({ uid: "u", email: "e" }, ""), /SESSION_SECRET/);
});
