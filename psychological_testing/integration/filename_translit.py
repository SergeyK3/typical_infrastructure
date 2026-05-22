"""ASCII-safe filenames: Russian → Latin transliteration (passport-style)."""

from __future__ import annotations

import re

# Lowercase Cyrillic → Latin (multi-char sequences processed via tuple order).
_RU_TO_LAT: tuple[tuple[str, str], ...] = (
    ("щ", "shch"),
    ("ш", "sh"),
    ("ч", "ch"),
    ("ц", "ts"),
    ("ю", "yu"),
    ("я", "ya"),
    ("ё", "e"),
    ("ж", "zh"),
    ("х", "kh"),
    ("ъ", ""),
    ("ь", ""),
    ("а", "a"),
    ("б", "b"),
    ("в", "v"),
    ("г", "g"),
    ("д", "d"),
    ("е", "e"),
    ("з", "z"),
    ("и", "i"),
    ("й", "y"),
    ("к", "k"),
    ("л", "l"),
    ("м", "m"),
    ("н", "n"),
    ("о", "o"),
    ("п", "p"),
    ("р", "r"),
    ("с", "s"),
    ("т", "t"),
    ("у", "u"),
    ("ф", "f"),
    ("ы", "y"),
    ("э", "e"),
)


def transliterate_ru(text: str) -> str:
    """Transliterate Cyrillic to Latin; other characters unchanged."""
    if not text:
        return ""
    out: list[str] = []
    i = 0
    while i < len(text):
        piece = text[i:].lower()
        original = text[i]
        matched: tuple[str, str] | None = None
        for src, dst in _RU_TO_LAT:
            if piece.startswith(src):
                matched = (src, dst)
                break
        if matched is not None:
            src, dst = matched
            repl = dst
            if original.isupper() and repl:
                repl = repl[0].upper() + repl[1:]
            out.append(repl)
            i += len(src)
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def ascii_slug_from_name(name: str, *, max_len: int = 60, fallback: str = "report") -> str:
    """``Kim Sergey Vasilevich`` → ``Kim_Sergey_Vasilievich``."""
    text = transliterate_ru(name.strip())
    text = re.sub(r"[^\w\s-]", "", text, flags=re.ASCII)
    text = re.sub(r"[\s_]+", "_", text.strip())
    text = text.strip("_")
    if not text:
        return fallback
    return text[:max_len]
