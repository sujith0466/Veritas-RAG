from pydantic import BaseModel, Field

class GoldenExampleDTO(BaseModel):
    query: str = Field(...)
    expected_answer: str = Field(...)
    expected_document_ids: list[str] = Field(default_factory=list)

class DatasetCreateDTO(BaseModel):
    name: str = Field(...)
    tenant_id: str = Field(...)
    examples: list[GoldenExampleDTO] = Field(...)

class EvaluationResultDTO(BaseModel):
    dataset_id: str = Field(...)
    precision: float = Field(..., ge=0.0, le=1.0)
    recall: float = Field(..., ge=0.0, le=1.0)
    f1_score: float = Field(..., ge=0.0, le=1.0)
    average_reliability_score: float = Field(..., ge=0.0, le=100.0)
    total_examples: int = Field(...)
