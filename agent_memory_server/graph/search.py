import logging

from agent_memory_server.models import MemoryRecordResult


logger = logging.getLogger(__name__)


def rrf_fusion(
    results_list: list[list[MemoryRecordResult]],
    k: int = 60,
) -> list[MemoryRecordResult]:
    score_map = {}
    doc_map = {}

    for results in results_list:
        if not results:
            continue
        for rank, result in enumerate(results):
            doc_id = result.id
            score = 1.0 / (k + rank + 1)
            current = score_map.get(doc_id, 0)
            score_map[doc_id] = current + score
            doc_map[doc_id] = result

    sorted_ids = sorted(score_map.items(), key=lambda x: x[1], reverse=True)

    fused_results = []
    for doc_id, fusion_score in sorted_ids:
        result = doc_map[doc_id]
        fused_result = result.model_copy(update={"score": fusion_score})
        fused_results.append(fused_result)

    return fused_results
