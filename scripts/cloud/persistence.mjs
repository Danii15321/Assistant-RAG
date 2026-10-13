/** Compare only persistent user content across a deployment; no credential output. */
import { readFile, writeFile } from 'node:fs/promises';
import { parseEnv } from 'node:util';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
const root = resolve(import.meta.dirname, '../..');
const require = createRequire(root + '/frontend/package.json');
const { Pool } = require('pg');
const mode = process.argv[2];
if (!['before', 'after'].includes(mode)) throw new Error('Explicit before/after required');
const path = root + '/evaluation/reports/persistence-step8.json';
const env = parseEnv(await readFile(root + '/evaluation/.qa/production.env', 'utf8'));
const pool = new Pool({ connectionString: env.DATABASE_URL_UNPOOLED, max: 1 });
const tables = ['documents', 'extracted_units', 'index_chunks', 'conversations', 'conversation_exchanges', 'conversation_sources'];
const snapshot = {};
try {
  for (const table of tables) {
    snapshot[table] = (await pool.query(`SELECT count(*)::int AS count,
      md5(coalesce(string_agg(t::text, E'\\n' ORDER BY t::text COLLATE "C"),'')) AS digest FROM ${table} t`)).rows[0];
  }
} finally { await pool.end(); }
if (!snapshot.conversations.count || snapshot.conversation_exchanges.count < 2 || !snapshot.index_chunks.count)
  throw new Error('Real indexed documents and conversation exchanges are required');
if (mode === 'before') {
  await writeFile(path, JSON.stringify({ date: new Date().toISOString(), before: snapshot }, null, 2) + '\n', { flag: 'wx' });
  console.log('Persistent data snapshot recorded before deployment');
} else {
  const report = JSON.parse(await readFile(path, 'utf8'));
  report.after = snapshot;
  report.checked_at = new Date().toISOString();
  report.passed = JSON.stringify(snapshot) === JSON.stringify(report.before);
  await writeFile(path, JSON.stringify(report, null, 2) + '\n');
  if (!report.passed) throw new Error('Persistent data changed; investigate before validation');
  console.log('Documents, vectors, conversations and citations unchanged after deployment');
}
