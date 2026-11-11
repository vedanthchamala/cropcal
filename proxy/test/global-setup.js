// Runs in Node before the Worker tests: brings the test database to the current
// schema. Start one with `pnpm db:test:up` (Postgres in Docker on port 54329).
import { migrate } from "../scripts/migrate.mjs";
import { TEST_DATABASE_URL } from "./db-url.js";

export default async function setup() {
  try {
    await migrate(TEST_DATABASE_URL, () => {});
  } catch (err) {
    throw new Error(
      `Worker tests need a Postgres at ${TEST_DATABASE_URL.replace(/:[^:@/]+@/, ":***@")} — run \`pnpm db:test:up\`. (${err.message})`
    );
  }
}
