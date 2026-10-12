"""Retain private index/retrieval and shared generation counters through replacements."""
import hashlib
import json
from pathlib import Path

from verify_index_persistence import run, snapshot
from verify_persistence import main as replace_database
from verify_search_persistence import retrieval

ROOT=Path(__file__).resolve().parents[2]
SOURCE=r"""
import json
from sqlalchemy import text
from app.config import Settings,build_engine
s=Settings()
assert s.database_url and s.database_url.endswith('/assistant_rag_test')
e=build_engine(s)
with e.connect() as c:
 attempts=[list(row) for row in c.execute(text('SELECT id::text,owner_id::text,created_at::text,reserved_tokens,prompt_tokens,completion_tokens,outcome FROM generation_attempts ORDER BY id'))]
 limits=[list(row) for row in c.execute(text('SELECT lease_token::text,lease_until::text,blocked_until::text FROM generation_limits'))]
print(json.dumps({'attempts':attempts,'limits':limits}))
e.dispose()
"""


def counters():
    return json.loads(run(['run','--rm','--no-deps','backend-auth-test','python','-'],SOURCE).stdout)


def main():
    before=snapshot(); searches=retrieval(); budgets=counters()
    if len(before)<18 or not budgets['attempts']:raise RuntimeError('Run the real browser suite first')
    try:
        replace_database()
        run(['up','-d','--no-deps','--force-recreate','--wait','backend-auth-test','worker-auth-test'])
        if before!=snapshot() or searches!=retrieval() or budgets!=counters():
            raise RuntimeError('Private indexes, search or shared counters changed')
        report={'status':'passed','environment':'local-test-only','documents_checked':len(before),
            'file_bytes_text_and_vectors_unchanged':True,'private_retrieval_unchanged':True,
            'generation_counters_unchanged':True,'attempts_checked':len(budgets['attempts']),
            'counters_sha256':hashlib.sha256(json.dumps(budgets,sort_keys=True).encode()).hexdigest(),
            'containers_replaced':['db','backend-auth-test','worker-auth-test'],'cloud_deployment':False}
        (ROOT/'evaluation/reports/answers-step6-persistence.json').write_text(json.dumps(report,indent=2)+'\n')
        print(f"Private search and generation persistence verified: {len(before)} documents, {len(budgets['attempts'])} attempts")
    finally:run(['stop','frontend-auth-test','backend-auth-test','worker-auth-test','llm-test'])


if __name__=='__main__':main()
