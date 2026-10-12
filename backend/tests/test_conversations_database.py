from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models.answer import AnswerResponse, AnswerSource, Claim, Evidence
from app.models.conversation import MessageRequest
from app.models.document import DocumentError
from app.repositories.conversations import ConversationRepository

pytest_plugins = ["test_documents"]
pytestmark = pytest.mark.integration


def start(context):
    engine, owners, *_ = context
    repo = ConversationRepository(engine)
    conversation = repo.create(owners[0])
    body = MessageRequest(
        request_id=uuid4(), question="Où a lieu le lancement ?", allow_external_processing=True
    )
    return repo, conversation, body


def response(context):
    from test_indexation import vectors
    from test_search_database import ready

    from app.repositories.search import SearchRepository

    engine, owners, *_ = context
    doc = ready(context)
    hit = SearchRepository(engine).candidates(owners[0], [doc.id], vectors(1)[0])[0]
    return doc, AnswerResponse(
        state="answered",
        answer="Réponse conservée [S1]",
        claims=[
            Claim(
                text="Réponse conservée", evidence=[Evidence(source_id="S1", quote=hit.text[:20])]
            )
        ],
        sources=[AnswerSource(**hit.model_dump(), source_id="S1")],
        provider_called=True,
        prompt_version="test",
        elapsed_ms=1,
    )


def test_owner_isolation_atomic_idempotency_and_serialization(context):
    repo, conversation, body = start(context)
    owners = context[1]
    with ThreadPoolExecutor(max_workers=2) as pool:
        entries = list(pool.map(lambda _: repo.begin(owners[0], conversation.id, body), range(2)))
    assert sum(created for _, created in entries) == 1
    assert entries[0][0].id == entries[1][0].id
    with pytest.raises(DocumentError, match="conversation_busy"):
        repo.begin(owners[0], conversation.id, body.model_copy(update={"request_id": uuid4()}))
    with pytest.raises(DocumentError, match="request_conflict"):
        repo.begin(
            owners[0], conversation.id, body.model_copy(update={"question": "Autre question"})
        )
    for action in [
        lambda: repo.get(owners[1], conversation.id),
        lambda: repo.messages(owners[1], conversation.id, 0, 20),
        lambda: repo.begin(owners[1], conversation.id, body),
        lambda: repo.delete(owners[1], conversation.id),
    ]:
        with pytest.raises(DocumentError) as error:
            action()
        assert error.value.status == 404
    assert repo.list(owners[1], 0, 20) == []
    assert len(repo.messages(owners[0], conversation.id, 0, 20)) == 1


def test_persisted_sources_scrubbed_at_exclusion_and_physical_delete(context):
    repo, conversation, body = start(context)
    owners = context[1]
    entry, _ = repo.begin(owners[0], conversation.id, body)
    doc, answer = response(context)
    repo.complete(owners[0], conversation.id, entry.id, answer, lambda: True)
    saved = repo.messages(owners[0], conversation.id, 0, 20)[0]
    assert saved.answer["claims"][0]["evidence"][0]["quote"] == answer.claims[0].evidence[0].quote
    context[2].delete(owners[0], doc.id)
    saved = repo.messages(owners[0], conversation.id, 0, 20)[0]
    assert saved.answer["answer"] == answer.answer
    assert saved.answer["sources"][0]["status"] == "deleted"
    assert saved.answer["sources"][0]["text"] == ""
    assert saved.answer["claims"][0]["evidence"][0]["quote"] == ""
    with context[0].connect() as c:
        assert (
            c.execute(
                text("SELECT payload ? 'text' OR payload ? 'quotes' FROM conversation_sources")
            ).scalar_one()
            is False
        )
        stored = c.execute(text("SELECT response FROM conversation_exchanges")).scalar_one()
        assert all(
            "quote" not in evidence for claim in stored["claims"] for evidence in claim["evidence"]
        )
    with context[0].begin() as c:
        c.execute(text("DELETE FROM documents WHERE id=:id"), {"id": doc.id})
    assert repo.messages(owners[0], conversation.id, 0, 20)[0].answer == saved.answer


def test_failed_pending_expiry_and_deleted_conversation_cannot_publish(context):
    repo, conversation, body = start(context)
    owner = context[1][0]
    entry, _ = repo.begin(owner, conversation.id, body)
    with context[0].begin() as c:
        c.execute(text("UPDATE conversations SET lease_until=now()-interval '1 second'"))
    assert repo.messages(owner, conversation.id, 0, 20)[0].error_code == "generation_interrupted"
    same, created = repo.begin(owner, conversation.id, body)
    assert same.state == "failed" and not created
    newer, _ = repo.begin(owner, conversation.id, body.model_copy(update={"request_id": uuid4()}))
    assert not repo.active(owner, conversation.id, entry.id)
    assert repo.active(owner, conversation.id, newer.id)
    repo.fail(owner, conversation.id, entry.id, "llm_unavailable")
    assert repo.active(owner, conversation.id, newer.id)
    repo.delete(owner, conversation.id)
    assert not repo.active(owner, conversation.id, newer.id)
    with pytest.raises(DocumentError, match="conversation_unavailable"):
        repo.complete(
            owner,
            conversation.id,
            newer.id,
            AnswerResponse(
                state="insufficient_context",
                answer="Absent",
                claims=[],
                sources=[],
                provider_called=False,
                prompt_version="test",
                elapsed_ms=1,
            ),
            lambda: True,
        )
    with context[0].connect() as c:
        assert c.execute(text("SELECT count(*) FROM conversation_exchanges")).scalar_one() == 0


def test_source_owner_constraints_publication_race_and_session(context):
    repo, conversation, body = start(context)
    owner = context[1][0]
    entry, _ = repo.begin(owner, conversation.id, body)
    doc, answer = response(context)
    with pytest.raises(DocumentError, match="session_expired"):
        repo.complete(owner, conversation.id, entry.id, answer, lambda: False)
    context[2].delete(owner, doc.id)
    with pytest.raises(DocumentError, match="source_unavailable"):
        repo.complete(owner, conversation.id, entry.id, answer, lambda: True)
    assert repo.messages(owner, conversation.id, 0, 20)[0].answer is None
    with pytest.raises(IntegrityError), context[0].begin() as c:
        c.execute(
            text(
                "INSERT INTO "
                "conversation_sources(exchange_id,owner_id,source_id,document_id,p"
                "ayload) VALUES (:exchange,:owner,'S1',:doc,'{}')"
            ),
            {"exchange": entry.id, "owner": context[1][1], "doc": doc.id},
        )

    from test_documents import uploaded

    foreign_doc = uploaded(context, owner_index=1)
    with pytest.raises(IntegrityError), context[0].begin() as c:
        c.execute(
            text(
                "INSERT INTO conversation_sources(exchange_id,owner_id,source_id,"
                "document_id,payload) "
                "VALUES (:exchange,:owner,'S1',:doc,'{}')"
            ),
            {"exchange": entry.id, "owner": owner, "doc": foreign_doc.id},
        )


def test_history_bounded_ordered_failed_questions_not_reused_and_quotas(context):
    repo, conversation, body = start(context)
    owner = context[1][0]
    for n in range(5):
        entry, _ = repo.begin(
            owner,
            conversation.id,
            body.model_copy(update={"request_id": uuid4(), "question": f"Question {n}"}),
        )
        if n == 3:
            repo.fail(owner, conversation.id, entry.id, "llm_unavailable")
        else:
            repo.complete(
                owner,
                conversation.id,
                entry.id,
                AnswerResponse(
                    state="insufficient_context",
                    answer=f"Réponse {n}",
                    claims=[],
                    sources=[],
                    provider_called=False,
                    prompt_version="test",
                    elapsed_ms=1,
                ),
                lambda: True,
            )
    history = repo.history(owner, conversation.id)
    assert len(history) == 6
    assert [h.content for h in history if h.role == "user"] == [
        "Question 1",
        "Question 2",
        "Question 4",
    ]
    assert len(repo.messages(owner, conversation.id, 1, 2)) == 2
    with context[0].begin() as c:
        c.execute(
            text("UPDATE conversations SET next_ordinal=101 WHERE id=:id"), {"id": conversation.id}
        )
    with pytest.raises(DocumentError, match="conversation_message_quota"):
        repo.begin(owner, conversation.id, body.model_copy(update={"request_id": uuid4()}))


def test_migration_rollback_preserves_auth_and_generation_budget(context, database):
    from app.repositories.generation import GenerationRepository

    repo, conversation, body = start(context)
    repo.begin(context[1][0], conversation.id, body)
    lease, _ = GenerationRepository(context[0]).acquire(context[1][0], "alice", 3100)
    GenerationRepository(context[0]).release(lease)
    command.downgrade(database[1], "0006_generation")
    command.upgrade(database[1], "head")
    with context[0].connect() as c:
        assert c.execute(text("SELECT count(*) FROM auth_session")).scalar_one() == 2
        assert c.execute(text("SELECT count(*) FROM generation_attempts")).scalar_one() == 1
        assert c.execute(text("SELECT count(*) FROM conversations")).scalar_one() == 0


def test_direct_physical_source_and_conversation_delete_keep_budget(context):
    from app.repositories.generation import GenerationRepository

    repo, conversation, body = start(context)
    owner = context[1][0]
    entry, _ = repo.begin(owner, conversation.id, body)
    doc, answer = response(context)
    repo.complete(owner, conversation.id, entry.id, answer, lambda: True)
    budget = GenerationRepository(context[0])
    lease, _ = budget.acquire(owner, "alice", 3100)
    budget.release(lease)
    with context[0].begin() as c:
        c.execute(text("DELETE FROM documents WHERE id=:id"), {"id": doc.id})
    saved = repo.messages(owner, conversation.id, 0, 20)[0]
    assert saved.answer["sources"][0]["status"] == "deleted"
    assert saved.answer["claims"][0]["evidence"][0]["quote"] == ""
    repo.delete(owner, conversation.id)
    with context[0].connect() as c:
        assert c.execute(text("SELECT count(*) FROM conversation_sources")).scalar_one() == 0
        assert c.execute(text("SELECT count(*) FROM generation_attempts")).scalar_one() == 1


def test_conversation_creation_quota_is_atomic(context):
    repo = ConversationRepository(context[0])
    owner = context[1][0]
    for _ in range(49):
        repo.create(owner)

    def create(_):
        try:
            return repo.create(owner).id
        except DocumentError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, range(2)))
    assert results.count("conversation_quota") == 1
    assert len(repo.list(owner, 0, 50)) == 50
