"""
latex_utils.py — Normalize LaTeX math expressions to readable English before indexing.

Handles two cases:
  1. Raw LaTeX strings in text: $\int_0^\infty x^2 dx$, \sigma, $$E=mc^2$$
  2. Garbled unicode from pypdf (already partially fixed by switching to PyMuPDF,
     but we still clean up any residual backslash commands)
"""
import re

# Ordered substitution table — more specific patterns first
_SUBSTITUTIONS = [
    # Fractions
    (r'\\frac\{([^{}]+)\}\{([^{}]+)\}', r'\1 divided by \2'),
    # Square root
    (r'\\sqrt\{([^{}]+)\}', r'square root of \1'),
    # Superscript / subscript (simple single char)
    (r'\^(\w)',          r' to the power \1'),
    (r'_(\w)',           r' subscript \1'),
    # Integrals
    (r'\\int(?:_\{[^}]*\})?\^?\{?[^}]*\}?', 'integral'),
    (r'\\iint',          'double integral'),
    (r'\\oint',          'contour integral'),
    # Sums / products
    (r'\\sum(?:_\{[^}]*\})?\^?\{?[^}]*\}?', 'sum'),
    (r'\\prod(?:_\{[^}]*\})?\^?\{?[^}]*\}?', 'product'),
    (r'\\lim(?:_\{[^}]*\})?', 'limit'),
    # Greek letters — lowercase
    (r'\\alpha',   'alpha'),
    (r'\\beta',    'beta'),
    (r'\\gamma',   'gamma'),
    (r'\\delta',   'delta'),
    (r'\\epsilon', 'epsilon'),
    (r'\\varepsilon', 'epsilon'),
    (r'\\zeta',    'zeta'),
    (r'\\eta',     'eta'),
    (r'\\theta',   'theta'),
    (r'\\vartheta','theta'),
    (r'\\iota',    'iota'),
    (r'\\kappa',   'kappa'),
    (r'\\lambda',  'lambda'),
    (r'\\mu',      'mu'),
    (r'\\nu',      'nu'),
    (r'\\xi',      'xi'),
    (r'\\pi',      'pi'),
    (r'\\varpi',   'pi'),
    (r'\\rho',     'rho'),
    (r'\\sigma',   'sigma'),
    (r'\\varsigma','sigma'),
    (r'\\tau',     'tau'),
    (r'\\upsilon', 'upsilon'),
    (r'\\phi',     'phi'),
    (r'\\varphi',  'phi'),
    (r'\\chi',     'chi'),
    (r'\\psi',     'psi'),
    (r'\\omega',   'omega'),
    # Greek letters — uppercase
    (r'\\Gamma',   'Gamma'),
    (r'\\Delta',   'Delta'),
    (r'\\Theta',   'Theta'),
    (r'\\Lambda',  'Lambda'),
    (r'\\Xi',      'Xi'),
    (r'\\Pi',      'Pi'),
    (r'\\Sigma',   'Sigma'),
    (r'\\Phi',     'Phi'),
    (r'\\Psi',     'Psi'),
    (r'\\Omega',   'Omega'),
    # Operators & relations
    (r'\\leq',     'less than or equal to'),
    (r'\\geq',     'greater than or equal to'),
    (r'\\neq',     'not equal to'),
    (r'\\approx',  'approximately equal to'),
    (r'\\equiv',   'equivalent to'),
    (r'\\sim',     'similar to'),
    (r'\\propto',  'proportional to'),
    (r'\\ll',      'much less than'),
    (r'\\gg',      'much greater than'),
    (r'\\pm',      'plus or minus'),
    (r'\\mp',      'minus or plus'),
    (r'\\times',   'times'),
    (r'\\div',     'divided by'),
    (r'\\cdot',    'dot'),
    (r'\\circ',    'composed with'),
    (r'\\oplus',   'direct sum'),
    (r'\\otimes',  'tensor product'),
    # Calculus / analysis
    (r'\\partial', 'partial derivative'),
    (r'\\nabla',   'gradient'),
    (r'\\infty',   'infinity'),
    (r'\\forall',  'for all'),
    (r'\\exists',  'there exists'),
    (r'\\in',      'in'),
    (r'\\notin',   'not in'),
    (r'\\subset',  'subset of'),
    (r'\\subseteq','subset of or equal to'),
    (r'\\cup',     'union'),
    (r'\\cap',     'intersection'),
    (r'\\emptyset','empty set'),
    # Arrows
    (r'\\rightarrow',     'implies'),
    (r'\\leftarrow',      'follows from'),
    (r'\\leftrightarrow', 'if and only if'),
    (r'\\Rightarrow',     'implies'),
    (r'\\Leftarrow',      'is implied by'),
    (r'\\Leftrightarrow', 'if and only if'),
    (r'\\to',             'to'),
    # Functions
    (r'\\log',   'log'),
    (r'\\ln',    'natural log'),
    (r'\\exp',   'exp'),
    (r'\\sin',   'sin'),
    (r'\\cos',   'cos'),
    (r'\\tan',   'tan'),
    (r'\\max',   'max'),
    (r'\\min',   'min'),
    (r'\\arg',   'arg'),
    (r'\\det',   'determinant'),
    (r'\\dim',   'dimension'),
    (r'\\ker',   'kernel'),
    (r'\\mathbb\{R\}', 'real numbers'),
    (r'\\mathbb\{Z\}', 'integers'),
    (r'\\mathbb\{N\}', 'natural numbers'),
    (r'\\mathbb\{Q\}', 'rational numbers'),
    (r'\\mathbb\{C\}', 'complex numbers'),
]

# Pre-compile all patterns
_COMPILED = [(re.compile(pat), repl) for pat, repl in _SUBSTITUTIONS]


def _apply_substitutions(expr: str) -> str:
    for pattern, replacement in _COMPILED:
        expr = pattern.sub(replacement, expr)
    # Strip remaining backslash commands: \foo → foo
    expr = re.sub(r'\\([a-zA-Z]+)', r'\1', expr)
    # Strip braces
    expr = re.sub(r'[{}]', ' ', expr)
    # Collapse whitespace
    expr = re.sub(r'  +', ' ', expr).strip()
    return expr


def normalize_math(text: str) -> str:
    """
    Normalize LaTeX math in text for better semantic embedding.

    - Display math $$...$$ → kept inline with normalized form appended
    - Inline math $...$ → normalized in place
    - Bare LaTeX commands outside math mode (e.g. \sigma in pypdf output) → normalized
    """
    if not text:
        return text

    # Display math: $$...$$
    def replace_display(m: re.Match) -> str:
        inner = m.group(1)
        normalized = _apply_substitutions(inner)
        return f"{inner} [{normalized}]" if normalized != inner else inner

    text = re.sub(r'\$\$(.+?)\$\$', replace_display, text, flags=re.DOTALL)

    # Inline math: $...$
    def replace_inline(m: re.Match) -> str:
        inner = m.group(1)
        normalized = _apply_substitutions(inner)
        return normalized if normalized else inner

    text = re.sub(r'\$([^$\n]+?)\$', replace_inline, text)

    return text
