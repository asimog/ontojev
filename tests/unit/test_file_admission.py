"""Open-file admission: no product is admitted without a named scientific consumer."""

from __future__ import annotations

from cancerjev.research.file_admission import (
    FILE_ADMISSION_VERSION,
    GRANTED_REASON,
    MAX_SINGLE_PRODUCT_FILE_BYTES,
    NAMED_FILE_CONSUMERS,
    AdmissionStatus,
    FileAccess,
    evaluate_file_admission,
)

CONSUMERS = {"SOME_METHOD_V1": "GENE_EXPRESSION_QUANTIFICATION"}


def _evaluate(**overrides):
    arguments = {
        "product_kind": "GENE_EXPRESSION_QUANTIFICATION",
        "project_id": "TCGA-LUAD",
        "consumer_method": "SOME_METHOD_V1",
        "file_count": 10,
        "total_bytes": 1024,
        "consumers": CONSUMERS,
    }
    arguments.update(overrides)
    return evaluate_file_admission(**arguments)


def test_no_consumer_is_declared_today_so_every_product_defers():
    assert NAMED_FILE_CONSUMERS == {}
    assert FILE_ADMISSION_VERSION == "1"

    decision = evaluate_file_admission(
        product_kind="GENE_EXPRESSION_QUANTIFICATION", project_id="TCGA-LUAD",
        consumer_method="SOME_METHOD_V1", file_count=10, total_bytes=1024,
    )
    assert decision.status is AdmissionStatus.DEFERRED
    assert decision.reason == "NO_NAMED_CONSUMER"


def test_unregistered_consumer_defers_even_with_a_complete_preflight():
    decision = _evaluate(consumer_method="UNREGISTERED_METHOD_V1")

    assert decision.status is AdmissionStatus.DEFERRED
    assert decision.reason == "NO_NAMED_CONSUMER"


def test_only_open_access_is_representable_at_all():
    assert [member.value for member in FileAccess] == ["OPEN"]
    assert not hasattr(FileAccess, "CONTROLLED")

    decision = _evaluate()
    assert decision.status is AdmissionStatus.ADMITTED
    assert decision.reason == GRANTED_REASON
    assert decision.decision_hash() == _evaluate().decision_hash()


def test_a_declared_consumer_with_a_mismatched_product_is_rejected():
    decision = _evaluate(product_kind="MASKED_SOMATIC_MUTATION")

    assert decision.status is AdmissionStatus.REJECTED
    assert decision.reason == "PRODUCT_NOT_DECLARED_FOR_CONSUMER"


def test_preflight_must_be_complete_before_admission():
    missing_bytes = _evaluate(total_bytes=None)
    missing_count = _evaluate(file_count=None)

    assert missing_bytes.status is AdmissionStatus.DEFERRED
    assert missing_bytes.reason == "PREFLIGHT_INCOMPLETE"
    assert missing_count.status is AdmissionStatus.DEFERRED


def test_multi_gigabyte_automatic_acquisition_is_rejected():
    decision = _evaluate(total_bytes=MAX_SINGLE_PRODUCT_FILE_BYTES + 1)

    assert decision.status is AdmissionStatus.REJECTED
    assert decision.reason == "MULTI_GB_AUTOMATIC_ACQUISITION_PROHIBITED"


def test_empty_selection_is_rejected():
    decision = _evaluate(file_count=0, total_bytes=0)

    assert decision.status is AdmissionStatus.REJECTED
    assert decision.reason == "NO_ELIGIBLE_FILES"


def test_admitted_decision_carries_its_manifest_and_is_deterministic():
    decision = _evaluate()

    assert decision.status is AdmissionStatus.ADMITTED
    assert decision.reason == GRANTED_REASON
    assert decision.payload()["file_count"] == 10
    assert decision.payload()["total_bytes"] == 1024
    assert decision.decision_hash() == _evaluate().decision_hash()
