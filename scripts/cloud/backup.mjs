/** Private export and local restore drill; never restores into a remote database. */
import { createRequire } from "node:module";
import { parseEnv } from "node:util";
import { readFile, mkdir, writeFile, chmod } from "node:fs/promises";
import { createWriteStream } from "node:fs";
import { resolve, join } from "node:path";
import { createHash, randomBytes } from "node:crypto";
import { spawnSync } from "node:child_process";
import { pipeline } from "node:stream/promises";
import { Readable } from "node:stream";

const root = resolve(import.meta.dirname, "../..");
const require = createRequire(join(root, "frontend/package.json"));
const { list, get } = require("@vercel/blob");
const { Pool } = require("pg");
const environment = process.argv[2];
if (!["preview", "production"].includes(environment)) throw new Error("Explicit environment required");
const env = parseEnv(await readFile(join(root, "evaluation/.qa", environment + ".env"), "utf8"));
const image = "pgvector/pgvector@sha256:ad249f9fb9572979643a47694e59b9a8cdcdf6abc6accebf49bb80ad5f20ff9b";
const destination = join(root, "evaluation/.qa/backups", environment + "-" + Date.now());
await mkdir(join(destination, "originals"), { recursive: true, mode: 0o700 });
await chmod(destination, 0o700);
const url = new URL(env.DATABASE_URL_UNPOOLED);
if (!url.hostname.endsWith(".neon.tech") || url.hostname.includes("-pooler.")) throw new Error("Direct Neon connection required");
const pgEnv = { ...process.env, PGHOST: url.hostname, PGUSER: decodeURIComponent(url.username),
  PGPASSWORD: decodeURIComponent(url.password), PGDATABASE: url.pathname.slice(1), PGSSLMODE: "verify-full" };
// Use the host trust bundle: the minimal PostgreSQL image has no CA bundle.
pgEnv.PGSSLROOTCERT = "/certs.pem";
function docker(args, options = {}) {
  const result = spawnSync("docker", args, { cwd: root, encoding: "utf8", maxBuffer: 10 * 1024 * 1024, ...options });
  if (result.status !== 0) {
    let diagnostic = result.stderr || result.error?.code || "unknown";
    for (const value of [...Object.values(env), pgEnv.PGPASSWORD].filter(v => v.length > 5)) diagnostic = diagnostic.split(value).join("[redacted]");
    throw new Error("Docker backup/restore failed: " + diagnostic.slice(-1800));
  }
  return result.stdout;
}
const pool = new Pool({ connectionString: env.DATABASE_URL_UNPOOLED, max: 1 });
const tables = ["documents", "extracted_units", "index_chunks", "conversations", "conversation_exchanges", "conversation_sources", "auth_user"];
const counts = {};
const digests = {};
const digestQuery = table => `SELECT md5(coalesce(string_agg(t::text, E'\\n' ORDER BY t::text),'')) AS digest FROM ${table} t`;
try {
  for (const table of tables) {
    // Fixed allowlist; missing table is a schema mismatch, never silently skipped.
    counts[table] = (await pool.query(`SELECT count(*)::int AS n FROM ${table}`)).rows[0].n;
    digests[table] = (await pool.query(digestQuery(table))).rows[0].digest;
  }
} finally { await pool.end(); }
docker(["run", "--rm", "--user", `${process.getuid()}:${process.getgid()}`, "--env", "PGHOST", "--env", "PGUSER", "--env", "PGPASSWORD", "--env", "PGDATABASE",
  "--env", "PGSSLMODE", "--env", "PGSSLROOTCERT", "--volume", "/etc/ssl/certs/ca-certificates.crt:/certs.pem:ro", "--volume", destination + ":/backup", image,
  "pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file=/backup/database.dump"], { env: pgEnv });
await chmod(join(destination, "database.dump"), 0o600);
const originals = [];
let cursor;
do {
  const page = await list({ token: env.BLOB_READ_WRITE_TOKEN, cursor, limit: 1000 });
  for (const blob of page.blobs) {
    if (!/^[a-f0-9-]{36}$/.test(blob.pathname)) throw new Error("Unexpected object key");
    const value = await get(blob.pathname, { access: "private", useCache: false, token: env.BLOB_READ_WRITE_TOKEN });
    if (!value || value.statusCode !== 200) throw new Error("Original unavailable");
    const path = join(destination, "originals", blob.pathname);
    await pipeline(Readable.fromWeb(value.stream), createWriteStream(path, { mode: 0o600 }));
    const raw = await readFile(path);
    originals.push({ id: blob.pathname, bytes: raw.length, sha256: createHash("sha256").update(raw).digest("hex") });
  }
  cursor = page.hasMore ? page.cursor : undefined;
} while (cursor);
const container = "assistant-rag-restore-" + randomBytes(5).toString("hex");
let started = false;
try {
  docker(["run", "-d", "--name", container, "--memory", "384m", "--env", "POSTGRES_HOST_AUTH_METHOD=trust",
    "--env", "POSTGRES_DB=assistant_rag_restore_test", "--volume", destination + ":/backup:ro", image]);
  started = true;
  for (let i = 0; i < 30; i++) {
    if (spawnSync("docker", ["exec", container, "pg_isready", "-U", "postgres"]).status === 0) break;
    await new Promise(r => setTimeout(r, 1000));
  }
  docker(["exec", container, "pg_restore", "-U", "postgres", "-d", "assistant_rag_restore_test",
    "--no-owner", "--no-acl", "--exit-on-error", "/backup/database.dump"]);
  for (const table of tables) {
    const count = Number(docker(["exec", container, "psql", "-U", "postgres", "-d", "assistant_rag_restore_test",
      "-Atc", `SELECT count(*) FROM ${table}`]).trim());
    if (count !== counts[table]) throw new Error("Restore count mismatch");
    const digest = docker(["exec", container, "psql", "-U", "postgres", "-d", "assistant_rag_restore_test",
      "-Atc", digestQuery(table)]).trim();
    if (digest !== digests[table]) throw new Error("Restore content mismatch (or writes during backup)");
  }
} finally {
  if (started) docker(["rm", "--force", "--volumes", container]);
}
const manifest = { environment, date: new Date().toISOString(), counts, digests, originals,
  dump_sha256: createHash("sha256").update(await readFile(join(destination, "database.dump"))).digest("hex"),
  restore: "passed", restore_target: "isolated local PostgreSQL 18; no exposed port" };
await writeFile(join(destination, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n", { mode: 0o600 });
await writeFile(join(root, "evaluation/reports/backup-step8-" + environment + ".json"),
  JSON.stringify({ ...manifest, originals: originals.map(({ bytes, sha256 }) => ({ bytes, sha256 })) }, null, 2) + "\n");
console.log("Private backup and isolated restore passed:", Object.values(counts).reduce((a,b)=>a+b,0), "rows,", originals.length, "originals");
