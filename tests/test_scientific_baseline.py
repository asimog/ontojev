"""Goldens captured before the typed transition at fb52305 (synthetic/offline).

Do not regenerate these to make a changed scientific identity pass. A deliberate
new version needs separate expectations; these protect historical interpretation.
"""

from cancerjev.domain.events import canonical_json
from cancerjev.domain.identity import (
    content_hash,
    evidence_state_identity_payload,
    statistical_state_identity_payload,
)
from cancerjev.domain.measurements import digest
from cancerjev.jev.projection import build_projection, projection_hash
from cancerjev.jev.questions import (
    deep_question_set_hash,
    hypothesis_question_set_hash,
    wide_question_set_hash,
)
from cancerjev.research.fixtures import evidence, statistical_states
from cancerjev.research.orchestrator import DemoOrchestrator
from tests.science.test_methods import _build, _frame


def test_pretransition_scientific_and_projection_goldens():
    fixture = statistical_states("golden", lambda name: name)[0]
    fixture["state_hash"] = content_hash(statistical_state_identity_payload(fixture))
    assert fixture["state_hash"] == "1695cdd28096fbf747043fdf695059060809513a78a44fc970781d531ad95fa5"
    revision = evidence("golden", "candidate", fixture, lambda name: name)
    assert content_hash(evidence_state_identity_payload(revision)) == (
        "f558ac40ded68024003b3d90cd38692099043e33f785001e27b458379fb4c2fd"
    )
    live = _build([_frame("TCGA-LUAD")])
    assert live["state_hash"] == "4df87b5c2b6ebca43b21f57c1958e0f3da59fce02a709c7f9824602fea8ca38b"
    projection = build_projection(live)
    assert projection_hash(projection) == "b93151e63b48ba43bea5e6b1376a852a67cfb30f2dee760821e38a69472c4752"
    assert canonical_json(projection) == canonical_json(build_projection(live))


def test_pretransition_question_definition_goldens():
    assert wide_question_set_hash() == "e515f2c182b8db0f50773bcd4dc5b8fc14ec8d2a7e264500f01dad3a1a5f3213"
    assert deep_question_set_hash() == "262d5ae47ce3ac77d1df0f27bb557cd4adb81f10e5cde8ebe034eb335c6ae9f1"
    assert hypothesis_question_set_hash() == "77f459d726ccd9455645a63d01cc8eba02cda768f07c0121767abee58b285894"


def test_fixture_event_type_and_stage_order_golden(runtime):
    settings, repository, artifacts = runtime
    emitted = []
    run_id = DemoOrchestrator(settings, repository, artifacts, emitted.append).run()
    assert repository.get_run(run_id)["status"] == "COMPLETED"
    assert len(emitted) == 71
    assert digest([(event["type"], event["stage"]) for event in emitted]) == (
        "cdd7da750e3a10613644594a5f7e3083ad9598adf32e08cf62b62db3aeb5d89a"
    )
