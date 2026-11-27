from dataclasses import dataclass

@dataclass(frozen=True)
class EmbeddingRequest:
    inputs: str
    normalize: bool = True
    truncate: bool = False
    truncation_direction: str = "Right"
    model_id: str = "tei"

@dataclass(frozen=True)
class EmbeddingResponse:
    model_id: str
    dimensions: int
    normalized: bool
    embedding: list[float]