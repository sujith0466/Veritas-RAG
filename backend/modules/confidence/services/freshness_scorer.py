from datetime import datetime, timezone
from dateutil import parser
from backend.modules.reliability.schemas.reliability_dto import ReliableCandidateDTO
from backend.modules.confidence.schemas.confidence_dto import FreshnessReportDTO


class FreshnessScorer:
    """Evaluates the temporal decay of retrieved evidence."""
    
    def __init__(self, decay_half_life_days: float = 365.0):
        # Default half-life is 1 year (chunk loses half its freshness score per year of age)
        self.decay_half_life_days = decay_half_life_days

    def analyze(self, candidates: list[ReliableCandidateDTO]) -> FreshnessReportDTO:
        """Calculate freshness score based on document metadata timestamps."""
        if not candidates:
            return FreshnessReportDTO(freshness_score=1.0, oldest_chunk_age_days=None)
            
        now = datetime.now(timezone.utc)
        max_age_days = 0.0
        total_score = 0.0
        scored_count = 0
        
        for c in candidates:
            created_at_str = c.metadata.get("created_at") or c.metadata.get("updated_at")
            if not created_at_str:
                continue
                
            try:
                dt = parser.isoparse(created_at_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                    
                age_days = (now - dt).days
                if age_days < 0:
                    age_days = 0.0
                    
                if age_days > max_age_days:
                    max_age_days = float(age_days)
                    
                # Exponential decay formula: Score = (0.5) ^ (age / half_life)
                # Cap minimum freshness at 0.2 to avoid completely zeroing out older but valid facts
                score = max(0.2, 0.5 ** (age_days / self.decay_half_life_days))
                total_score += score
                scored_count += 1
            except Exception:
                pass
                
        # If no candidates had valid timestamps, default to 1.0 (perfectly fresh)
        avg_freshness = total_score / scored_count if scored_count > 0 else 1.0
        
        return FreshnessReportDTO(
            freshness_score=avg_freshness,
            oldest_chunk_age_days=max_age_days if scored_count > 0 else None
        )
