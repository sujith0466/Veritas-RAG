from pydantic import BaseModel, ConfigDict, Field


class WorkspacePolicyDTO(BaseModel):
    max_tokens: int | None = Field(default=None, description="Max allowed tokens per generation")
    blocked_topics: list[str] = Field(default_factory=list, description="Topics to block")
    redact_pii: bool | None = Field(default=None, description="Whether to redact PII")
    block_jailbreaks: bool | None = Field(default=None, description="Whether to block prompt injection")

    model_config = ConfigDict(from_attributes=True)

class TenantPolicyDTO(BaseModel):
    max_tokens: int | None = Field(default=None, description="Max allowed tokens per generation")
    blocked_topics: list[str] = Field(default_factory=list, description="Topics to block")
    redact_pii: bool | None = Field(default=None, description="Whether to redact PII")
    block_jailbreaks: bool | None = Field(default=None, description="Whether to block prompt injection")

    model_config = ConfigDict(from_attributes=True)

class MergedPolicyDTO(BaseModel):
    max_tokens: int = Field(default=4096)
    blocked_topics: list[str] = Field(default_factory=list)
    redact_pii: bool = Field(default=True)
    block_jailbreaks: bool = Field(default=True)

    model_config = ConfigDict(from_attributes=True)
