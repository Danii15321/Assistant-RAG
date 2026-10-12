import math
from collections.abc import Sequence

MODEL_ID = "intfloat/multilingual-e5-small"
MODEL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
DIMENSION = 384
PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "
INDEX_VERSION = f"canonical-v1|split-v1:300:50|{MODEL_ID}@{MODEL_REVISION}|384|prefix-v1|l2"


def validate_vectors(vectors: Sequence[Sequence[float]], expected: int) -> None:
    if len(vectors) != expected or expected < 1:
        raise ValueError("embedding_batch")
    for vector in vectors:
        if len(vector) != DIMENSION or not all(math.isfinite(v) for v in vector):
            raise ValueError("embedding_dimension")
        norm = math.sqrt(sum(v * v for v in vector))
        if abs(norm - 1) > 0.001:
            raise ValueError("embedding_normalization")
