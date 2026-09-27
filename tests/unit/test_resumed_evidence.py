"""Unit guards for the declared evidence-resume loader."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cancerjev.domain.discovery import (
    EXPRESSION_TAIL_METHOD_ID,
    EXPRESSION_TAIL_VERSION,
    REDUCER_METHOD_ID,
    REDUCER_VERSION,
)
from cancerjev.domain.measurements import MetricAvailability
from cancerjev.research.acquisition import LiveRunError
from cancerjev.research.resumed_evidence import (
    _require_current_methods,
    load_resumed_evidence,
)


def test_resume_refuses_a_retired_mutation_reducer():
    stale = SimpleNamespace(reducer=SimpleNamespace(
        method_id="MUTATION_AFFECTED_CASE_COUNT_V1", version="1"))

    with pytest.raises(LiveRunError) as excinfo:
        _require_current_methods("mutation", stale)

    assert excinfo.value.code == "EVIDENCE_RESUME_STALE_METHOD"


def test_resume_refuses_stale_observed_expression_tails():
    stale = SimpleNamespace(entries=[SimpleNamespace(tail=SimpleNamespace(
        availability=MetricAvailability.OBSERVED,
        method=SimpleNamespace(method_id="EXPRESSION_TUKEY_TAIL_V1", version="1")))])

    with pytest.raises(LiveRunError) as excinfo:
        _require_current_methods("expression", stale)

    assert excinfo.value.code == "EVIDENCE_RESUME_STALE_METHOD"


def test_resume_accepts_current_method_identities():
    current_reducer = SimpleNamespace(reducer=SimpleNamespace(
        method_id=REDUCER_METHOD_ID, version=REDUCER_VERSION))
    current_tails = SimpleNamespace(entries=[SimpleNamespace(tail=SimpleNamespace(
        availability=MetricAvailability.OBSERVED,
        method=SimpleNamespace(method_id=EXPRESSION_TAIL_METHOD_ID,
                               version=EXPRESSION_TAIL_VERSION)))])

    _require_current_methods("mutation", current_reducer)
    _require_current_methods("expression", current_tails)


def test_resume_requires_at_least_one_source():
    with pytest.raises(LiveRunError) as excinfo:
        load_resumed_evidence(repository=None, artifacts=None, spec=None)

    assert excinfo.value.code == "EVIDENCE_RESUME_SOURCE_MISSING"
