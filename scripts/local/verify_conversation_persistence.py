"""Verify historical exchanges, removable sources and budgets on isolated volumes."""
import hashlib
import json
from pathlib import Path

from verify_generation_persistence import counters
from verify_index_persistence import run, snapshot
from verify_persistence import main as replace_database
from verify_search_persistence import retrieval

ROOT = Path(__file__).resolve().parents[2]
SOURCE = r"""
import json
from sqlalchemy import text
from app.config import Settings,build_engine
s=Settings()
assert s.database_url and s.database_url.endswith('/assistant_rag_test')
e=build_engine(s)
result={}
with e.connect() as c:
 for table in ['conversations','conversation_exchanges','conversation_sources']:
  result[table]=[row[0] for row in c.execute(text(f'SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text'))]
print(json.dumps(result,sort_keys=True,default=str))
e.dispose()
"""


def history():
    return json.loads(run(['run', '--rm', '--no-deps', 'backend-auth-test', 'python', '-'], SOURCE).stdout)


def main():
    before = snapshot(); searches = retrieval(); budgets = counters(); saved = history()
    sources = saved['conversation_sources']
    if not saved['conversation_exchanges'] or not sources or not budgets['attempts']:
        raise RuntimeError('Run the browser conversation suite first')
    if not any(s['status'] == 'deleted' for s in sources) or not any(s['status'] == 'available' for s in sources):
        raise RuntimeError('Persistence requires available and deleted historical sources')
    if any('text' in s['payload'] or 'quotes' in s['payload'] for s in sources if s['status'] == 'deleted'):
        raise RuntimeError('Deleted citations still contain text')
    try:
        replace_database()
        run(['up', '-d', '--no-deps', '--force-recreate', '--wait', 'backend-auth-test', 'worker-auth-test'])
        if before != snapshot() or searches != retrieval() or budgets != counters() or saved != history():
            raise RuntimeError('Private data changed during container replacements')
        report = {'status': 'passed', 'environment': 'local-test-only',
                  'documents_checked': len(before), 'conversations_checked': len(saved['conversations']),
                  'exchanges_checked': len(saved['conversation_exchanges']), 'sources_checked': len(sources),
                  'available_sources': sum(s['status'] == 'available' for s in sources),
                  'deleted_sources': sum(s['status'] == 'deleted' for s in sources),
                  'file_bytes_text_and_vectors_unchanged': True, 'private_retrieval_unchanged': True,
                  'generation_counters_unchanged': True, 'history_and_sources_unchanged': True,
                  'deleted_source_excerpts_absent': True, 'attempts_checked': len(budgets['attempts']),
                  'history_sha256': hashlib.sha256(json.dumps(saved, sort_keys=True).encode()).hexdigest(),
                  'containers_replaced': ['db', 'backend-auth-test', 'worker-auth-test'], 'cloud_deployment': False}
        (ROOT / 'evaluation/reports/conversations-step7-persistence.json').write_text(json.dumps(report, indent=2) + '\n')
        print(f"Conversation persistence verified: {len(saved['conversations'])} conversations, {len(saved['conversation_exchanges'])} exchanges, {len(sources)} sources")
    finally:
        run(['stop', 'frontend-auth-test', 'backend-auth-test', 'worker-auth-test', 'llm-test'])


if __name__ == '__main__':
    main()
