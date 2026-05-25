from __future__ import annotations

import re
from dataclasses import dataclass, field

CF_RE = re.compile(r"\b[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]\b", re.I)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
TEL_RE = re.compile(r"(?<!\w)(?:\+39\s?)?(?:\d[\s.-]?){8,14}\d(?!\w)")
NAME_RE = re.compile(r"\b([A-Z][a-zàèéìòù]{2,})(?:\s+([A-Z][a-zàèéìòù]{2,}))?\b")

@dataclass
class PseudonymizationResult:
    text: str
    mapping: dict[str, str] = field(default_factory=dict)

    def restore(self, value: str) -> str:
        restored = value
        for placeholder, original in self.mapping.items():
            restored = restored.replace(placeholder, original)
        return restored


def _replace(pattern: re.Pattern, text: str, prefix: str, mapping: dict[str, str]) -> str:
    reverse = {original: placeholder for placeholder, original in mapping.items()}

    def repl(match: re.Match) -> str:
        original = match.group(0)
        if original in reverse:
            return reverse[original]
        placeholder = f"[{prefix}_{sum(1 for key in mapping if key.startswith('[' + prefix + '_')) + 1}]"
        mapping[placeholder] = original
        return placeholder

    return pattern.sub(repl, text)


def pseudonymize_prompt(text: str) -> PseudonymizationResult:
    mapping: dict[str, str] = {}
    result = _replace(CF_RE, text, "CF", mapping)
    result = _replace(EMAIL_RE, result, "EMAIL", mapping)
    result = _replace(TEL_RE, result, "TEL", mapping)
    result = _replace(NAME_RE, result, "NOME", mapping)
    return PseudonymizationResult(text=result, mapping=mapping)
