"""Bounded generated text, deliberately separate from scientific evidence."""

from dataclasses import dataclass

from cancerjev.domain._json import obj, seq, string
from cancerjev.domain.measurements import ContractError

HYPOTHESIS_LABEL = "GENERATED FIXTURE HYPOTHESIS"
MAX_TEXT_CHARS = 2000
MAX_LIST_ITEMS = 10
DRAFT_FIELDS = ("statement", "proposed_mechanism", "predictions", "contradicted_if",
                "distinguishing_tests", "required_evidence", "unsupported_assumptions")


def _text(value: object) -> str:
    result = string(value)
    if not result.strip() or len(result) > MAX_TEXT_CHARS:
        raise ContractError("hypothesis text must be nonblank and at most 2000 characters")
    return result


@dataclass(frozen=True)
class HypothesisDraft:
    label: str
    generator: str
    generator_model: str | None
    statement: str
    proposed_mechanism: str
    predictions: tuple[str, ...]
    contradicted_if: tuple[str, ...]
    distinguishing_tests: tuple[str, ...]
    required_evidence: tuple[str, ...]
    unsupported_assumptions: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.label)
        _text(self.generator)
        if self.generator_model is not None:
            _text(self.generator_model)
        _text(self.statement)
        _text(self.proposed_mechanism)
        for values in (self.predictions, self.contradicted_if, self.distinguishing_tests,
                       self.required_evidence, self.unsupported_assumptions):
            if type(values) is not tuple or len(values) > MAX_LIST_ITEMS:
                raise ContractError("hypothesis lists must be bounded immutable tuples")
            for value in values:
                _text(value)


def read_hypothesis_draft(value: object, *, allowed_action_ids: frozenset[str], label: str,
                          generator: str, generator_model: str | None = None) -> HypothesisDraft:
    record = obj(value, " ".join(DRAFT_FIELDS))
    lists = {key: tuple(_text(item) for item in seq(record[key])) for key in DRAFT_FIELDS[2:]}
    if not set(lists["distinguishing_tests"]) <= allowed_action_ids:
        raise ContractError("hypothesis names an unknown or ineligible registered action")
    return HypothesisDraft(label, generator, generator_model, _text(record["statement"]),
                           _text(record["proposed_mechanism"]),
                           lists["predictions"], lists["contradicted_if"], lists["distinguishing_tests"],
                           lists["required_evidence"], lists["unsupported_assumptions"])

