// Mints RS256 ID tokens with a throwaway key, plus the JWKS a verifier would fetch.
const b64url = (buf) => Buffer.from(buf).toString("base64url");

export async function makeIssuer(kid = "test-kid") {
  const pair = await crypto.subtle.generateKey(
    { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
    true,
    ["sign", "verify"]
  );
  const pub = await crypto.subtle.exportKey("jwk", pair.publicKey);
  const jwks = { keys: [{ kty: pub.kty, n: pub.n, e: pub.e, kid, alg: "RS256", use: "sig" }] };
  async function idToken(claims, { headerKid = kid, alg = "RS256" } = {}) {
    const head = b64url(JSON.stringify({ alg, kid: headerKid, typ: "JWT" }));
    const body = b64url(JSON.stringify(claims));
    const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", pair.privateKey, new TextEncoder().encode(`${head}.${body}`));
    return `${head}.${body}.${b64url(sig)}`;
  }
  return { jwks, idToken };
}
