from __future__ import annotations

import pytest

from cancerjev.research.fixtures import (
    CHOICE_ROSTERS,
    SCORE_LEVELS,
    choice_answer,
    judgment_vector,
    score_answer,
)


def _assert_distribution(distribution: dict[str, float], roster: tuple[str, ...]) -> None:
    assert set(distribution) == set(roster)
    assert all(isinstance(value, float) for value in distribution.values())
    assert all(0 <= value <= 1 for value in distribution.values())
    assert abs(sum(distribution.values()) - 1) <= 0.002


def test_choice_answers_match_their_rosters():
    for question_id, roster in CHOICE_ROSTERS.items():
        for chosen in roster:
            answer = choice_answer(question_id, chosen, 0.8, 0.79)
            assert answer["chosen"] == chosen
            assert answer["chosen"] in answer["distribution"]
            _assert_distribution(answer["distribution"], roster)


def test_choice_rejects_options_outside_the_roster():
    with pytest.raises(ValueError, match="roster"):
        choice_answer("deep_route", "WEAKENED", 0.5, 0.5)
    with pytest.raises(ValueError, match="within"):
        choice_answer("deep_route", "FOLLOW_UP", 1.5, 0.5)


def test_score_answers_stay_inside_the_zero_to_four_rubric():
    for level in range(len(SCORE_LEVELS)):
        answer = score_answer(level, 0.76)
        assert answer["selected"] == level
        assert set(answer["distribution"]) <= set(SCORE_LEVELS)
        assert set(answer["legend"]) == set(SCORE_LEVELS)
        assert abs(sum(answer["distribution"].values()) - 1) <= 0.002
        expected = sum(int(level_key) * share for level_key, share in answer["distribution"].items())
        assert 0 <= answer["expected"] <= len(SCORE_LEVELS) - 1
        assert abs(answer["expected"] - expected) < 0.01


def test_score_rejects_levels_outside_the_rubric():
    with pytest.raises(ValueError, match="0..4"):
        score_answer(5, 0.5)
    with pytest.raises(ValueError, match="0..4"):
        score_answer(-1, 0.5)


def test_judgment_vectors_are_contract_valid():
    vectors = [
        judgment_vector("wide_pattern_route", "PROMOTE", 0.88, 4),
        judgment_vector("wide_pattern_route", "DEFER", 0.3, 1),
        judgment_vector("deep_route", "FOLLOW_UP", 0.82, 3),
        judgment_vector("followup_outcome", "WEAKENED", 0.84, 2),
        judgment_vector("hypothesis_testability", "TESTABLE", 0.78, 3),
    ]
    for vector in vectors:
        assert 0 <= vector["noul"]["probability"] <= 1
        choice = vector["choice"]
        assert choice["chosen"] in choice["distribution"]
        _assert_distribution(choice["distribution"], CHOICE_ROSTERS[choice["question_id"]])
        score = vector["score"]
        assert score["selected"] in range(len(SCORE_LEVELS))
        assert set(score["distribution"]) == set(SCORE_LEVELS)
        assert abs(sum(score["distribution"].values()) - 1) <= 0.002
        assert set(score["legend"]) == set(SCORE_LEVELS)
