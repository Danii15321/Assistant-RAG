from pathlib import Path
from unittest.mock import Mock

from app.worker.query import QueryWorker


def test_query_worker_uses_query_mode_and_refuses_silent_truncation():
    repository, encoder = Mock(), Mock()
    encoder.model_path = Path("/unused")
    repository.claim.return_value = {"question": "Question"}
    encoder.encode.return_value = [[1.0] + [0.0] * 383]
    worker = QueryWorker(repository, encoder)
    worker.tokenizer = Mock()
    worker.tokenizer.offsets.return_value = [(0, 1)] * 510
    assert worker.run_once()
    encoder.encode.assert_called_once_with(["Question"], "query")
    worker.tokenizer.offsets.return_value = [(0, 1)] * 511
    encoder.reset_mock()
    assert worker.run_once()
    encoder.encode.assert_not_called()
    assert repository.finish.call_args.kwargs["error"] == "query_too_long"


def test_query_worker_error_is_technical_and_not_an_empty_search_result():
    repository, encoder = Mock(), Mock()
    encoder.model_path = Path("/unused")
    repository.claim.return_value = {"question": "Question"}
    encoder.encode.side_effect = RuntimeError("unavailable")
    worker = QueryWorker(repository, encoder)
    worker.tokenizer = Mock()
    worker.tokenizer.offsets.return_value = [(0, 1)]
    assert worker.run_once()
    assert repository.finish.call_args.kwargs["error"] == "search_unavailable"
