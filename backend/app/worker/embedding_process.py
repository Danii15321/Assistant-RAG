"""Isolated CPU encoder; stdout contains only the bounded result for its parent."""

import json
import os
import sys
from pathlib import Path

from app.services.embeddings import PASSAGE_PREFIX, QUERY_PREFIX


def main() -> None:
    os.environ.update(
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        TOKENIZERS_PARALLELISM="false",
        OMP_NUM_THREADS="1",
    )
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    path = Path(sys.argv[1])
    model = SentenceTransformer(str(path), device="cpu", local_files_only=True)

    def encode_payload(payload: object, mode: str) -> str:
        if not isinstance(payload, list) or not 1 <= len(payload) <= 16:
            raise ValueError("embedding_batch")
        if mode not in {"passage", "query"} or not all(isinstance(item, str) for item in payload):
            raise ValueError("embedding_batch")
        prefix = PASSAGE_PREFIX if mode == "passage" else QUERY_PREFIX
        inputs = [prefix + item for item in payload]
        if any(len(ids) > 512 for ids in model.tokenizer(inputs, truncation=False)["input_ids"]):
            raise ValueError("embedding_token_limit")
        vectors = model.encode(
            inputs,
            batch_size=16,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return json.dumps(vectors.tolist())

    if sys.argv[2] == "--server":
        while line := sys.stdin.buffer.readline(1024 * 1024 + 1):
            if len(line) > 1024 * 1024 or not line.endswith(b"\n"):
                raise ValueError("embedding_batch")
            request = json.loads(line)
            print(encode_payload(request["texts"], request["mode"]), flush=True)
            del request, line
    else:
        texts = json.loads(sys.stdin.buffer.read(1024 * 1024 + 1))
        print(encode_payload(texts, sys.argv[2]))


if __name__ == "__main__":
    main()
