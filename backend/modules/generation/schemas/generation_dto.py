from pydantic import BaseModel, Field


class CitationDTO(BaseModel):
    citation_index: int = Field(..., description="1-based index of the citation marker in the answer text, e.g. [1]")
    chunk_id: str = Field(..., description="The source chunk ID")
    document_id: str = Field(..., description="The source document ID")
    excerpt: str = Field(..., description="Verbatim excerpt from the chunk that supports the cited claim")
    relevance_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Relevance of this citation to the cited claim")


class GenerationRequestDTO(BaseModel):
    query: str = Field(..., description="The user's original or rewritten query")
    evidence_chunks: list[dict] = Field(..., description="List of evidence chunks (id, content, document_id) to generate from")
    correlation_id: str = Field(..., description="Request tracking ID for tracing")
    max_answer_tokens: int = Field(default=1024, ge=64, le=4096, description="Max token budget for the generated answer")


class GroundedAnswerDTO(BaseModel):
    answer_text: str = Field(..., description="The generated answer with inline citation markers e.g. [1], [2]")
    citations: list[CitationDTO] = Field(default_factory=list, description="Ordered list of citations matching inline markers")
    is_fully_grounded: bool = Field(..., description="True if every sentence in the answer has at least one citation")
    correlation_id: str = Field(..., description="Request tracking ID")
    evidence_used_count: int = Field(..., description="Number of evidence chunks used in the answer")
