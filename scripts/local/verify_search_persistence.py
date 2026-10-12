"""Verify retained files/vectors and identical private retrieval after service replacement."""
import json
from pathlib import Path

from verify_index_persistence import run, snapshot

ROOT=Path(__file__).resolve().parents[2]
SOURCE=r'''
import json,hashlib
from sqlalchemy import text
from app.config import Settings,build_engine
from app.repositories.search import SearchRepository
s=Settings()
if not s.database_url or not s.database_url.endswith('/assistant_rag_test'):raise RuntimeError('Dedicated test database required')
e=build_engine(s)
repository=SearchRepository(e)
result=[]
with e.connect() as c:
 rows=c.execute(text("SELECT DISTINCT ON (d.id) d.id,d.owner_id,c.embedding::text FROM documents d JOIN index_chunks c ON c.document_id=d.id AND c.owner_id=d.owner_id AND c.generation=d.generation WHERE d.state='ready' AND c.embedding IS NOT NULL ORDER BY d.id,c.ordinal")).all()
for identifier,owner,vector in rows:
 hits=repository.candidates(owner,[identifier],json.loads(vector))
 payload=[h.model_dump(mode='json') for h in hits]
 result.append({'id':str(identifier),'retrieval_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()})
e.dispose()
print(json.dumps(result))
'''


def retrieval():
    return json.loads(run(['run','--rm','--no-deps','backend-auth-test','python','-'],SOURCE).stdout)


def main():
    before=snapshot()
    searches=retrieval()
    if len(before)<10 or len(searches)!=len(before):raise RuntimeError('Run the browser import/search suite first')
    try:
        run(['up','-d','--no-deps','--force-recreate','--wait','backend-auth-test','worker-auth-test'])
        if before!=snapshot() or searches!=retrieval():raise RuntimeError('Private index/retrieval changed after replacement')
        report={'status':'passed','environment':'local-test-only','documents_checked':len(before),
            'file_bytes_text_and_vectors_unchanged':True,'private_retrieval_unchanged':True,
            'containers_replaced':['backend-auth-test','worker-auth-test'],'cloud_deployment':False}
        (ROOT/'evaluation/reports/search-step5-persistence.json').write_text(json.dumps(report,indent=2)+'\n')
        print(f'Private index and search persistence verified: {len(before)} test documents')
    finally:run(['stop','frontend-auth-test','backend-auth-test','worker-auth-test'])


if __name__=='__main__':main()
