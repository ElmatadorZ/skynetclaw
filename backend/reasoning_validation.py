"""
reasoning_validation.py — DEPRECATED SHIM
=========================================
The Reasoning Validation Layer has been superseded by the Cognitive Validation
Layer (CVL): the framework now validates every cognitive capability
(reasoning · memory · planning · tool_use · safety · production), not just
reasoning. Arithmetic is now the first *cognitive* validator (domain=reasoning).

This module remains only for backward compatibility — it re-exports CVL so any
older `import reasoning_validation` keeps working. New code should
`import cognitive_validation`.

See docs/adr/ADR-0002-cognitive-validation-layer.md.
"""
from cognitive_validation import (  # noqa: F401
    DOMAINS,
    Issue,
    ValidationResult,
    Validator,
    ArithmeticValidator,
    register,
    registered,
    by_domain,
    validate,
)
