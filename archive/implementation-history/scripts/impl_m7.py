import os


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created {path}")

# 1. DTOs
retry_dto = '''"""Data Transfer Objects (`DTOs`) for the Retry Controller."""

from pydantic import BaseModel, Field, ConfigDict
from enum import StrEnum
from uuid import UUID
from backend.modules.confidence.schemas.confidence_dto import ConfidenceResultDTOv2

class RetryReason(StrEnum):
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    LLM_API_ERROR = "LLM_API_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    MALFORMED_OUTPUT = "MALFORMED_OUTPUT"
    UNKNOWN = "UNKNOWN"

class RetryAction(StrEnum):
    RETRY_IMMEDIATE = "RETRY_IMMEDIATE"
    RETRY_WITH_BACKOFF = "RETRY_WITH_BACKOFF"
    RETRY_WITH_REWRITE = "RETRY_WITH_REWRITE"
    RETRY_WITH_FALLBACK_MODEL = "RETRY_WITH_FALLBACK_MODEL"
    ABORT = "ABORT"

class RetryContextDTO(BaseModel):
    query_id: str
    tenant_id: str
    attempt_number: int = Field(..., ge=1, le=4)
    max_retries: int = Field(3, description="Hard cap of 3 retries per PRD")
    reason: RetryReason
    last_confidence: ConfidenceResultDTOv2 | None = None
    error_message: str | None = None
    model_config = ConfigDict(from_attributes=True)

class RetryDecisionDTO(BaseModel):
    action: RetryAction
    backoff_ms: int = Field(0, ge=0, le=10000)
    reason_code: str
    is_budget_exhausted: bool = False
    is_monotonic_regression: bool = False
    model_config = ConfigDict(from_attributes=True)

class RetryRuleDTO(BaseModel):
    reason: RetryReason
    action: RetryAction
    base_backoff_ms: int
    max_attempts_for_rule: int
    model_config = ConfigDict(from_attributes=True)

class RetryPolicyDTO(BaseModel):
    tenant_id: str
    max_total_retries: int = Field(3, le=3)
    rules: list[RetryRuleDTO]
    model_config = ConfigDict(from_attributes=True)
'''
write_file("backend/modules/retry/schemas/retry_dto.py", retry_dto)

# 2. Errors
errors = '''"""Retry-specific exceptions."""

from backend.core.exceptions.base import RAGuardException

class RetryBudgetExhaustedError(RAGuardException):
    def __init__(self, message: str = "Retry budget exhausted"):
        super().__init__(message=message, error_code="RET_BUDGET_EXHAUSTED")

class RetryMonotonicRegressionError(RAGuardException):
    def __init__(self, message: str = "Retry attempt yielded worse confidence than previous"):
        super().__init__(message=message, error_code="RET_MONOTONIC_REGRESSION")
'''
write_file("backend/modules/retry/schemas/errors.py", errors)

# 3. Rule Engine
rule_engine = '''"""Rule Engine. Maps errors to actions using priority ordering."""

from backend.modules.retry.schemas.retry_dto import RetryReason, RetryAction, RetryDecisionDTO, RetryRuleDTO

class RuleEngine:
    def __init__(self):
        # Default fallback rules
        self.default_rules = [
            RetryRuleDTO(reason=RetryReason.RATE_LIMIT, action=RetryAction.RETRY_WITH_BACKOFF, base_backoff_ms=1000, max_attempts_for_rule=3),
            RetryRuleDTO(reason=RetryReason.LLM_API_ERROR, action=RetryAction.RETRY_WITH_BACKOFF, base_backoff_ms=500, max_attempts_for_rule=2),
            RetryRuleDTO(reason=RetryReason.LOW_CONFIDENCE, action=RetryAction.RETRY_WITH_REWRITE, base_backoff_ms=0, max_attempts_for_rule=2),
            RetryRuleDTO(reason=RetryReason.TIMEOUT, action=RetryAction.RETRY_WITH_FALLBACK_MODEL, base_backoff_ms=200, max_attempts_for_rule=1),
            RetryRuleDTO(reason=RetryReason.MALFORMED_OUTPUT, action=RetryAction.RETRY_IMMEDIATE, base_backoff_ms=0, max_attempts_for_rule=1),
        ]
        
    def evaluate(self, reason: RetryReason, custom_rules: list[RetryRuleDTO] | None = None) -> RetryRuleDTO:
        rules = custom_rules if custom_rules else self.default_rules
        for rule in rules:
            if rule.reason == reason:
                return rule
        return RetryRuleDTO(reason=RetryReason.UNKNOWN, action=RetryAction.ABORT, base_backoff_ms=0, max_attempts_for_rule=0)
'''
write_file("backend/modules/retry/services/rule_engine.py", rule_engine)

# 4. Policy Engine
policy_engine = '''"""Policy Engine. Fetches and enforces tenant-specific retry policies."""

from backend.modules.retry.schemas.retry_dto import RetryPolicyDTO, RetryRuleDTO, RetryReason, RetryAction
from typing import Any

class PolicyEngine:
    def __init__(self, cache_provider: Any = None):
        self.cache_provider = cache_provider

    async def get_policy(self, tenant_id: str) -> RetryPolicyDTO:
        # Stub: Return default policy
        return RetryPolicyDTO(
            tenant_id=tenant_id,
            max_total_retries=3,
            rules=[]
        )
'''
write_file("backend/modules/retry/services/policy_engine.py", policy_engine)

# 5. Budget Manager
budget_manager = '''"""Retry Budget Manager. Enforces hard caps via Redis."""

from typing import Any

class RetryBudgetManager:
    def __init__(self, cache_provider: Any = None):
        self.cache_provider = cache_provider
        self.hard_cap = 3

    async def check_budget(self, tenant_id: str, query_id: str, attempt_number: int) -> bool:
        """Returns True if budget is available, False if exhausted."""
        if attempt_number > self.hard_cap:
            return False
            
        # Optional: check global tenant token/retry limits via Redis
        return True
        
    async def consume_budget(self, tenant_id: str, query_id: str) -> None:
        pass
'''
write_file("backend/modules/retry/services/budget_manager.py", budget_manager)

# 6. Decision Engine
decision_engine = '''"""Decision Engine. Enforces monotonic improvements and aggregates rules."""

from backend.modules.retry.schemas.retry_dto import RetryDecisionDTO, RetryContextDTO, RetryAction, RetryReason
from backend.modules.retry.services.rule_engine import RuleEngine
from backend.modules.retry.services.budget_manager import RetryBudgetManager
from backend.modules.retry.services.policy_engine import PolicyEngine

class DecisionEngine:
    def __init__(self):
        self.rule_engine = RuleEngine()
        self.budget_manager = RetryBudgetManager()
        self.policy_engine = PolicyEngine()

    async def decide(self, context: RetryContextDTO) -> RetryDecisionDTO:
        # 1. Budget Check
        has_budget = await self.budget_manager.check_budget(context.tenant_id, context.query_id, context.attempt_number)
        if not has_budget:
            return RetryDecisionDTO(action=RetryAction.ABORT, reason_code="BUDGET_EXHAUSTED", is_budget_exhausted=True)
            
        # 2. Policy Fetch
        policy = await self.policy_engine.get_policy(context.tenant_id)
        if context.attempt_number > policy.max_total_retries:
            return RetryDecisionDTO(action=RetryAction.ABORT, reason_code="POLICY_LIMIT_REACHED")
            
        # 3. Rule Evaluation
        rule = self.rule_engine.evaluate(context.reason, policy.rules)
        if rule.action == RetryAction.ABORT:
            return RetryDecisionDTO(action=RetryAction.ABORT, reason_code="NO_MATCHING_RULE_OR_ABORT")
            
        # Exponential backoff calculation
        backoff = rule.base_backoff_ms * (2 ** (context.attempt_number - 1))
        
        return RetryDecisionDTO(
            action=rule.action,
            backoff_ms=backoff,
            reason_code="RULE_MATCHED"
        )

    def check_monotonicity(self, current_score: float, previous_score: float) -> bool:
        """Returns True if improvement is monotonic, False if regression."""
        return current_score >= previous_score
'''
write_file("backend/modules/retry/services/decision_engine.py", decision_engine)

# 7. Retry Controller
retry_controller = '''"""Master Retry Controller (ExecutionGateway v2)."""

import asyncio
from typing import Any
from backend.modules.retry.schemas.retry_dto import RetryContextDTO, RetryReason, RetryAction, RetryDecisionDTO
from backend.modules.retry.services.decision_engine import DecisionEngine
from backend.modules.confidence.schemas.confidence_dto import ConfidenceResultDTOv2

class RetryController:
    def __init__(self):
        self.decision_engine = DecisionEngine()
        self.history = {} # query_id -> list of confidence scores

    async def handle_retry(self, context: RetryContextDTO) -> RetryDecisionDTO:
        # Store confidence history for monotonicity checks
        if context.last_confidence:
            hist = self.history.get(context.query_id, [])
            if hist:
                if not self.decision_engine.check_monotonicity(context.last_confidence.score, hist[-1]):
                    return RetryDecisionDTO(
                        action=RetryAction.ABORT,
                        reason_code="MONOTONIC_REGRESSION",
                        is_monotonic_regression=True
                    )
            hist.append(context.last_confidence.score)
            self.history[context.query_id] = hist

        # Get decision
        decision = await self.decision_engine.decide(context)
        
        # Apply sleep if backoff
        if decision.action == RetryAction.RETRY_WITH_BACKOFF and decision.backoff_ms > 0:
            await asyncio.sleep(decision.backoff_ms / 1000.0)
            
        return decision
'''
write_file("backend/modules/retry/services/retry_controller.py", retry_controller)

# 8. Routes
routes = '''"""Retry API Routes."""
from fastapi import APIRouter
from backend.modules.retry.schemas.retry_dto import RetryContextDTO, RetryDecisionDTO
from backend.modules.retry.services.retry_controller import RetryController

router = APIRouter()
controller = RetryController()

@router.post("/decide", response_model=RetryDecisionDTO)
async def decide_retry(context: RetryContextDTO):
    return await controller.handle_retry(context)
'''
write_file("backend/modules/retry/api/routes.py", routes)
os.makedirs("backend/modules/retry/api", exist_ok=True)
with open("backend/modules/retry/api/__init__.py", "w") as f: f.write("")

# 9. Alembic
migration = '''"""retry_controller_logs

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'retry_decision_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('query_id', sa.String(50), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(50), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('backoff_ms', sa.Integer(), nullable=False),
        sa.Column('is_regression', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

def downgrade():
    op.drop_table('retry_decision_logs')
'''
write_file("alembic/versions/0011_retry_controller_logs.py", migration)

print("impl_m7 part 1 completed.")
