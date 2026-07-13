from latex_utils import normalize_math


def test_normalize_math_empty_string_returns_empty():
    assert normalize_math("") == ""


def test_normalize_math_inline_greek_letter():
    assert normalize_math("The value $\\sigma$ represents variance.") == "The value sigma represents variance."


def test_normalize_math_inline_fraction():
    result = normalize_math("Compute $\\frac{a}{b}$ now.")
    assert result == "Compute a divided by b now."


def test_normalize_math_display_math_keeps_original_and_appends_normalized():
    result = normalize_math("Given $$\\alpha + \\beta$$ here.")
    assert result == "Given \\alpha + \\beta [alpha + beta] here."


def test_normalize_math_leaves_plain_text_untouched():
    assert normalize_math("No math here at all.") == "No math here at all."


def test_normalize_math_strips_bare_backslash_commands_in_inline_math():
    result = normalize_math("Limit as $x \\to \\infty$")
    assert "to" in result and "infinity" in result
