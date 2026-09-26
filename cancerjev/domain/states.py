from enum import StrEnum


class RunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class CandidateStatus(StrEnum):
    NEW = "NEW"
    WIDE_EVALUATED = "WIDE_EVALUATED"
    DEEP_ANALYZED = "DEEP_ANALYZED"
    HYPOTHESIZED = "HYPOTHESIZED"
    FOLLOWUP = "FOLLOWUP"
    DOSSIER_READY = "DOSSIER_READY"
    CANDIDATE_COMPLETE = "CANDIDATE_COMPLETE"
    TERMINATED = "TERMINATED"
    DEFERRED = "DEFERRED"
    FAILED = "FAILED"


TERMINAL_CANDIDATE_STATUSES = frozenset({
    CandidateStatus.CANDIDATE_COMPLETE,
    CandidateStatus.TERMINATED,
    CandidateStatus.DEFERRED,
    CandidateStatus.FAILED,
})
NON_TERMINAL_CANDIDATE_STATUSES = frozenset(CandidateStatus) - TERMINAL_CANDIDATE_STATUSES

# Declared candidate lifecycle. Candidates are born through an INSERT (NEW or
# WIDE_EVALUATED) and every later UPDATE must move along one of these edges.
# DEEP_ANALYZED self-loops because every accepted evidence revision re-asserts it,
# and HYPOTHESIZED -> DEEP_ANALYZED is the hypothesis-driven test landing a new
# revision. A terminal status has no outgoing edge: a completed candidate is never
# rewritten.
CANDIDATE_TRANSITIONS = {
    CandidateStatus.NEW: {CandidateStatus.WIDE_EVALUATED, CandidateStatus.DEFERRED,
                          CandidateStatus.FAILED},
    CandidateStatus.WIDE_EVALUATED: {CandidateStatus.DEEP_ANALYZED, CandidateStatus.FOLLOWUP,
                                     CandidateStatus.DEFERRED, CandidateStatus.FAILED},
    CandidateStatus.DEEP_ANALYZED: {CandidateStatus.DEEP_ANALYZED, CandidateStatus.FOLLOWUP,
                                    CandidateStatus.HYPOTHESIZED, CandidateStatus.DOSSIER_READY,
                                    CandidateStatus.DEFERRED, CandidateStatus.FAILED},
    CandidateStatus.FOLLOWUP: {CandidateStatus.DEEP_ANALYZED, CandidateStatus.DOSSIER_READY,
                               CandidateStatus.DEFERRED, CandidateStatus.FAILED},
    CandidateStatus.HYPOTHESIZED: {CandidateStatus.DEEP_ANALYZED, CandidateStatus.DOSSIER_READY,
                                   CandidateStatus.DEFERRED, CandidateStatus.FAILED},
    CandidateStatus.DOSSIER_READY: {CandidateStatus.CANDIDATE_COMPLETE, CandidateStatus.FAILED},
    CandidateStatus.CANDIDATE_COMPLETE: frozenset(),
    CandidateStatus.TERMINATED: frozenset(),
    CandidateStatus.DEFERRED: frozenset(),
    CandidateStatus.FAILED: frozenset(),
}


def validate_candidate_transition(current: str, target: str) -> None:
    try:
        current_status = CandidateStatus(current)
        target_status = CandidateStatus(target)
    except ValueError as exc:
        raise ValueError("unknown candidate status") from exc
    if target_status not in CANDIDATE_TRANSITIONS[current_status]:
        raise ValueError(
            f"illegal candidate transition: {current_status} -> {target_status}")


# Crash recovery never rewrites a candidate that already owns its dossier or reached
# a terminal state; only in-flight candidates are deferred. DOSSIER_READY is stable
# for recovery even though its lifecycle edge to CANDIDATE_COMPLETE still exists.
RECOVERY_PRESERVED_CANDIDATE_STATUSES = (
    TERMINAL_CANDIDATE_STATUSES | {CandidateStatus.DOSSIER_READY})
RECOVERY_DEFERRABLE_CANDIDATE_STATUSES = (
    frozenset(CandidateStatus) - RECOVERY_PRESERVED_CANDIDATE_STATUSES)


STAGES = (
    "INVENTORY", "GDC_FAST_SEARCH", "STATE_GENERATION", "JEV_WIDE",
    "DEEP_ANALYSIS", "EVIDENCE_BUILD", "JEV_DEEP", "HYPOTHESIS_GENERATION",
    "HYPOTHESIS_VERIFICATION", "FOLLOWUP", "DOSSIER", "FINALIZATION", "PROGRAM",
)

