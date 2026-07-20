from pydantic import BaseModel, Field


class RewriteRequestDTO(BaseModel):
    original_query: str = Field(..., description="The original ambiguous or complex query")
    context_hints: list[str] = Field(default_factory=list, description="Optional context hints to guide rewriting")


class DecomposedQueriesDTO(BaseModel):
    original_query: str = Field(..., description="The original query")
    sub_queries: list[str] = Field(default_factory=list, description="The decomposed independent search queries")
    is_complex: bool = Field(..., description="True if the query needed decomposition")


class HyDEResponseDTO(BaseModel):
    original_query: str = Field(..., description="The original query")
    hypothetical_document: str = Field(..., description="The generated hypothetical document")
    embedding_query: str = Field(..., description="The combined text used for embedding search")


class ClarificationQuestionDTO(BaseModel):
    question_text: str = Field(..., description="The clarifying question to present to the user")
    options: list[str] = Field(default_factory=list, description="Suggested multiple choice answers if applicable")
