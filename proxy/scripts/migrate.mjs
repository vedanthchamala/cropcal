// Applies proxy/migrations/*.sql in name order, once each, inside a transaction.
//   DATABASE_URL=postgres://... node proxy/scripts/migrate.mjs
// Migrations are additive only; a rollback is a new migration.
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import pg from "pg";

const DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "migrations");

export async function migrate(connectionString, log = console.log) {
  const client = new pg.Client({ connectionString });
  await client.connect();
  try {
    await client.query(
      "create table if not exists schema_migrations (name text primary key, applied_at timestamptz not null default now())"
    );
    const done = new Set((await client.query("select name from schema_migrations")).rows.map((r) => r.name));
    for (const name of readdirSync(DIR).filter((f) => f.endsWith(".sql")).sort()) {
      if (done.has(name)) continue;
      await client.query("begin");
      try {
        await client.query(readFileSync(join(DIR, name), "utf8"));
        await client.query("insert into schema_migrations (name) values ($1)", [name]);
        await client.query("commit");
        log(`applied ${name}`);
      } catch (err) {
        await client.query("rollback");
        throw new Error(`${name}: ${err.message}`);
      }
    }
  } finally {
    await client.end();
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const url = process.env.DATABASE_URL;
  if (!url) {
    console.error("DATABASE_URL is not set");
    process.exit(1);
  }
  await migrate(url);
  console.log("migrations up to date");
}
