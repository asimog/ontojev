"""Measured observations: typed action-produced evidence, never a synthetic check."""

from __future__ import annotations

import pytest

from cancerjev.domain.evidence import MeasuredObservation
from cancerjev.domain.measurements import ContractError


def _observation(**overrides):
    arguments = {
        "method_id": "MUTATION_CANONICAL_COMPOSITION_V1",
        "method_version": "1",
        "evidence_kind": "MUTATION_CANONICAL_COMPOSITION",
        "observed": b'{"consequence_composition": [["missense_variant", 3]]}',
        "availability": "OBSERVED",
        "n_effective": 3,
        "population_hash": "a" * 64,
        "limitations": ("descriptive only; no p-values",),
    }
    arguments.update(overrides)
    return MeasuredObservation(**arguments)


def test_measured_observation_is_typed_and_boundary_decodable():
    observation = _observation()

    assert observation.availability == "OBSERVED" and observation.reason is None
    assert observation.n_effective == 3
    assert observation.population_hash == "a" * 64


def test_unavailable_observation_requires_its_reason_and_decodable_payload():
    with pytest.raises(ContractError):
        _observation(availability="NOT_OBSERVED", n_effective=None)
    unavailable = _observation(availability="NOT_OBSERVED", n_effective=None,
                               reason="PAGE_CAP_REACHED")
    assert unavailable.reason == "PAGE_CAP_REACHED"

    with pytest.raises(ContractError):
        _observation(observed=b"not-json")
    with pytest.raises(ContractError):
        _observation(availability="MAYBE")
    with pytest.raises(ContractError):
        _observation(population_hash="short")
