"""Direct characterization of utils.token_manager -- pure functions, no DB/app context needed."""
from conftest import make_message
from config import Config
from utils import token_manager


def test_estimate_tokens_empty_string_is_zero():
    assert token_manager.estimate_tokens("") == 0


def test_estimate_tokens_whitespace_only_is_one_not_zero():
    # `not text` is False for a non-empty whitespace string, so this falls
    # through to word-splitting (zero words found) and the max(1, ...) floor
    # -- current behavior is 1, not 0. Pinned down explicitly so the Step 3
    # port doesn't accidentally "fix" this into a silent behavior change.
    assert token_manager.estimate_tokens("   ") == 1


def test_estimate_tokens_scales_with_word_count():
    assert token_manager.estimate_tokens("hello world") == 2
    assert token_manager.estimate_tokens("a") == 1


def test_get_total_tokens_sums_token_counts():
    messages = [make_message("user", "a", token_count=10), make_message("user", "b", token_count=25)]
    assert token_manager.get_total_tokens(messages) == 35


def test_is_over_limit_boundary_is_strictly_greater_than():
    threshold = Config.MAX_TOKENS - Config.TOKEN_SAFETY_MARGIN
    at_threshold = [make_message("user", "x", token_count=threshold)]
    over_threshold = [make_message("user", "x", token_count=threshold + 1)]

    assert token_manager.is_over_limit(at_threshold) is False
    assert token_manager.is_over_limit(over_threshold) is True


def test_get_token_stats_percentage_is_relative_to_max_tokens_not_safety_margin():
    messages = [make_message("user", "x", token_count=2000)]
    stats = token_manager.get_token_stats(messages)

    assert stats["current_tokens"] == 2000
    assert stats["max_tokens"] == Config.MAX_TOKENS
    assert stats["percentage"] == round(2000 / Config.MAX_TOKENS * 100, 2)
