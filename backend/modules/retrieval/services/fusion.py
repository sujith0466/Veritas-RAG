"""Reciprocal Rank Fusion (`RRF`) and Near-Duplicate Deduplication Engine (`FusionEngine`).

Implements mathematical rank merging (`ADR-M4-001`) combining dense vector search (`Qdrant`)
and sparse keyword matching (`BM25`) candidate lists across heterogeneous score scales,
and performs high-speed near-duplicate content filtering (`ADR-M4-002`) before reranking.
"""

from uuid import UUID

from structlog import get_logger

from backend.modules.retrieval.providers.sparse.bm25_provider import tokenize
from backend.modules.retrieval.schemas.retrieval_dto import CandidatePointDTO, RankedEvidenceDTO

logger = get_logger(__name__)


def compute_jaccard_similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Compute Jaccard token set similarity between two chunk token sets."""
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a.intersection(tokens_b))
    union = len(tokens_a.union(tokens_b))
    return float(intersection) / float(union) if union > 0 else 0.0


class FusionEngine:
    """Orchestrates Reciprocal Rank Fusion (`RRF`) and candidate deduplication (`ADR-005`)."""

    @staticmethod
    def execute_rrf_fusion(
        dense_candidates: list[CandidatePointDTO],
        sparse_candidates: list[CandidatePointDTO],
        rrf_k: int = 60,
    ) -> list[RankedEvidenceDTO]:
        """Combine dense and sparse candidate lists using Reciprocal Rank Fusion (`ADR-M4-001`).

        Formula:
            RRF_Score(d) = sum_{m in {dense, sparse}} ( 1 / (rrf_k + rank_m(d)) )

        Args:
            dense_candidates: Candidates returned from Qdrant vector search.
            sparse_candidates: Candidates returned from BM25 keyword matching.
            rrf_k: Constant smoothing parameter (default 60).

        Returns:
            List of RankedEvidenceDTO merged by chunk_id and ordered descending by rrf_score.
        """
        # Map chunk_id to merged information
        merged_map: dict[UUID, dict[str, Any]] = {}

        # Process dense candidates
        for item in dense_candidates:
            cid = item.chunk_id
            score_contrib = 1.0 / (float(rrf_k) + float(item.rank))
            if cid not in merged_map:
                merged_map[cid] = {
                    "chunk_id": cid,
                    "document_id": item.document_id,
                    "document_version_id": item.document_version_id,
                    "tenant_id": item.tenant_id,
                    "content": item.content,
                    "dense_rank": item.rank,
                    "sparse_rank": None,
                    "rrf_score": score_contrib,
                    "matched_sources": ["dense"],
                    "metadata": item.metadata,
                }
            else:
                merged_map[cid]["dense_rank"] = item.rank
                merged_map[cid]["rrf_score"] += score_contrib
                if "dense" not in merged_map[cid]["matched_sources"]:
                    merged_map[cid]["matched_sources"].append("dense")

        # Process sparse candidates
        for item in sparse_candidates:
            cid = item.chunk_id
            score_contrib = 1.0 / (float(rrf_k) + float(item.rank))
            if cid not in merged_map:
                merged_map[cid] = {
                    "chunk_id": cid,
                    "document_id": item.document_id,
                    "document_version_id": item.document_version_id,
                    "tenant_id": item.tenant_id,
                    "content": item.content,
                    "dense_rank": None,
                    "sparse_rank": item.rank,
                    "rrf_score": score_contrib,
                    "matched_sources": ["sparse"],
                    "metadata": item.metadata,
                }
            else:
                merged_map[cid]["sparse_rank"] = item.rank
                merged_map[cid]["rrf_score"] += score_contrib
                if "sparse" not in merged_map[cid]["matched_sources"]:
                    merged_map[cid]["matched_sources"].append("sparse")

        # Sort descending by rrf_score
        merged_list = list(merged_map.values())
        merged_list.sort(key=lambda x: x["rrf_score"], reverse=True)

        ranked_evidence: list[RankedEvidenceDTO] = []
        for idx, entry in enumerate(merged_list, start=1):
            evidence = RankedEvidenceDTO(
                chunk_id=entry["chunk_id"],
                document_id=entry["document_id"],
                document_version_id=entry["document_version_id"],
                tenant_id=entry["tenant_id"],
                content=entry["content"],
                dense_rank=entry["dense_rank"],
                sparse_rank=entry["sparse_rank"],
                rrf_score=round(float(entry["rrf_score"]), 6),
                rerank_score=None,
                final_rank=idx,
                matched_sources=entry["matched_sources"],
                metadata=entry["metadata"],
            )
            ranked_evidence.append(evidence)

        logger.debug(
            "Completed RRF rank fusion",
            dense_in=len(dense_candidates),
            sparse_in=len(sparse_candidates),
            merged_out=len(ranked_evidence),
        )
        return ranked_evidence

    @staticmethod
    def deduplicate_candidates(
        candidates: list[RankedEvidenceDTO],
        similarity_threshold: float = 0.92,
    ) -> list[RankedEvidenceDTO]:
        """Eliminate near-duplicate semantic chunks (`ADR-M4-002`) while preserving highest rank.

        Computes token set Jaccard similarity across merged candidates. If two distinct chunk IDs
        have similarity >= similarity_threshold, the lower-ranked candidate is filtered out.

        Args:
            candidates: List of RankedEvidenceDTO ordered descending by RRF score.
            similarity_threshold: Token Jaccard similarity threshold for near-duplicate rejection (default 0.92).

        Returns:
            Surviving unique list of RankedEvidenceDTO re-indexed with contiguous final_rank.
        """
        if not candidates:
            return []

        surviving: list[RankedEvidenceDTO] = []
        # Precompute token sets for surviving candidates to avoid repeated tokenization
        surviving_token_sets: list[set[str]] = []

        deduped_count = 0
        for item in candidates:
            item_tokens = set(tokenize(item.content))
            is_dup = False

            # Check similarity against all higher-ranked surviving candidates
            for s_tokens in surviving_token_sets:
                sim = compute_jaccard_similarity(item_tokens, s_tokens)
                if sim >= similarity_threshold:
                    is_dup = True
                    deduped_count += 1
                    break

            if not is_dup:
                surviving.append(item)
                surviving_token_sets.append(item_tokens)

        # Re-index final_rank strictly 1-to-N
        for idx, s_item in enumerate(surviving, start=1):
            s_item.final_rank = idx

        if deduped_count > 0:
            logger.debug(
                "Filtered near-duplicate retrieval candidates",
                input_count=len(candidates),
                deduped_count=deduped_count,
                surviving_count=len(surviving),
            )

        return surviving
