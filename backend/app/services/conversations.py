from collections.abc import Callable
from uuid import UUID

from app.models.answer import AnswerRequest
from app.models.conversation import Exchange, MessageRequest
from app.models.document import DocumentError
from app.repositories.conversations import ConversationRepository
from app.services.answers import AnswerService


class ConversationService:
    def __init__(self, repository: ConversationRepository, answers: AnswerService) -> None:
        self.repository, self.answers = repository, answers

    def execute(
        self,
        owner: UUID,
        session: str,
        conversation: UUID,
        body: MessageRequest,
        active_session: Callable[[], bool],
    ) -> Exchange:
        exchange, created = self.repository.begin(owner, conversation, body)
        if not created:
            return exchange

        def active() -> bool:
            if not active_session():
                return False
            if not self.repository.active(owner, conversation, exchange.id):
                raise DocumentError(409, "generation_interrupted")
            return True

        try:
            # Read at most six persisted messages; only the last two successful user
            # questions disambiguate retrieval. Assistant text is never evidence.
            history = self.repository.history(owner, conversation)
            answer = self.answers.execute(
                owner,
                session,
                AnswerRequest(
                    model=body.model,
                    question=body.question,
                    document_ids=body.document_ids,
                    allow_external_processing=body.allow_external_processing,
                    history=[message for message in history if message.role == "user"][-2:],
                ),
                active,
            )
            return self.repository.complete(
                owner, conversation, exchange.id, answer, active_session
            )
        except DocumentError as error:
            self.repository.fail(owner, conversation, exchange.id, error.code)
            raise
        except Exception:
            self.repository.fail(owner, conversation, exchange.id, "service_unavailable")
            raise
