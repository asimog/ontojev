from dataclasses import FrozenInstanceError, replace

import pytest

from cancerjev.domain.actions import ComputedEvidenceRevision, IntegrityCheck
from cancerjev.domain.events import canonical_json
from cancerjev.jev.contracts import EvaluationRecord, ValidatedAnswers
from cancerjev.research.deep import DeepError, FollowUpResult
from cancerjev.research.ranking import baseline_ranking, jev_ranking
from tests.jev.stub_adapter import StubAdapter
from tests.jev.test_service import _service
from tests.science.test_methods import _build, _frame


def test_typed_evaluation_and_cache_preserve_policy_and_boundary_bytes(runtime):
    adapter = StubAdapter()
    service, context = _service(runtime, adapter)
    state = _build([_frame("P1")], typed=True)
    first = service.evaluate_record(run_id=context["run_id"], state=state, emit=context["emit"])
    second = service.evaluate_record(run_id=context["run_id"], state=state, emit=context["emit"])
    assert isinstance(first, EvaluationRecord) and isinstance(first.answers, ValidatedAnswers)
    assert first.error_code is None and second.error_code is None
    assert adapter.calls == 1
    assert second.answers == first.answers
    assert second.cache_source_evaluation_id == first.evaluation_id
    assert canonical_json(jev_ranking([state.summary], [first])) == canonical_json(
        jev_ranking([state.boundary_representation()], [first.boundary_representation()]))
    assert canonical_json(baseline_ranking([state.summary])) == canonical_json(
        baseline_ranking([state.boundary_representation()]))
    copy = first.boundary_representation()
    copy["answers"].clear()
    assert first.answers.answers and first.boundary_representation()["answers"]
    with pytest.raises(FrozenInstanceError):
        first.answers.answers = ()


def test_revision_checks_and_summary_cannot_drift():
    checks = (IntegrityCheck("c", "claim", "VERIFIED", b"{}", b"{}", 1, (), ()),)
    revision = ComputedEvidenceRevision("e", "f" * 64, "candidate", "parent", 1, "action", checks, b"{}")
    result = FollowUpResult("COMPLETED", "action", "e", "f" * 64, 1, 1, 1, 0, 0, None, revision)
    assert result.revision.check_summary.verified == 1
    with pytest.raises(DeepError, match="check summary mismatch"):
        replace(result, checks_verified=0)
    with pytest.raises(DeepError, match="binding"):
        replace(result, evidence_hash="a" * 64)
