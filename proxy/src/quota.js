// One instance per invite code (named "code:<token>") plus one named "global".
// SQLite-backed storage with the synchronous kv API: each method reads, decides
// and writes with no intervening I/O, which the runtime guarantees is atomic
// per object — so N parallel requests on one code get exactly `limit` yeses.
import { DurableObject } from "cloudflare:workers";
import { releaseIn, reserveIn, usedIn } from "./lib.js";

const KEY = "s";

export class QuotaCounter extends DurableObject {
  reserve({ day, limit, burst }) {
    const r = reserveIn(this.ctx.storage.kv.get(KEY), { day, limit, burst, now: Date.now() });
    this.ctx.storage.kv.put(KEY, r.state);
    return { ok: r.ok, reason: r.reason || null, used: r.used };
  }

  release(day) {
    const next = releaseIn(this.ctx.storage.kv.get(KEY), day);
    if (next) this.ctx.storage.kv.put(KEY, next);
  }

  used(day) {
    return usedIn(this.ctx.storage.kv.get(KEY), day);
  }
}
