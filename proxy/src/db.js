// Postgres through the Hyperdrive binding. Holds accounts and usage metadata
// only — never image or page content. Quotas do not live here: they stay in
// the QuotaCounter Durable Object so a database outage cannot lift a limit.
import pg from "pg";

export const dbConfigured = (env) => Boolean(env.HYPERDRIVE?.connectionString);

// One client per request; Hyperdrive pools the real connections.
export async function withDb(env, fn) {
  if (!dbConfigured(env)) throw new Error("database not configured");
  const client = new pg.Client({ connectionString: env.HYPERDRIVE.connectionString });
  // The Workers socket reports "socket has been closed" as an error event after
  // a normal end(); without a listener that becomes an unhandled rejection.
  client.on("error", () => {});
  await client.connect();
  try {
    return await fn(client);
  } finally {
    await client.end().catch(() => {});
  }
}

const USER_COLS = "id, email, daily_limit, disabled";

export async function upsertUser(db, { sub, email }) {
  const r = await db.query(
    `insert into users (google_sub, email) values ($1, $2)
     on conflict (google_sub) do update set email = excluded.email, last_seen_at = now()
     returning ${USER_COLS}`,
    [sub, email]
  );
  return r.rows[0];
}

export async function getUser(db, id) {
  const r = await db.query(`select ${USER_COLS} from users where id = $1`, [id]);
  return r.rows[0] || null;
}

export async function insertUsage(db, e) {
  await db.query(
    `insert into usage_events
       (user_id, caller, status, model, latency_ms, prompt_tokens, output_tokens, thought_tokens, event_count)
     values ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
    [
      e.userId ?? null, e.caller, e.status, e.model ?? null, e.latencyMs ?? null,
      e.promptTokens ?? null, e.outputTokens ?? null, e.thoughtTokens ?? null, e.eventCount ?? null
    ]
  );
}
