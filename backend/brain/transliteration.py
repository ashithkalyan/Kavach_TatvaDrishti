"""
KAVACH Brain — Transliteration & Script Layer
=================================================
Extends alias_resolver.py with TWO more resolution mechanisms that are
linguistically distinct from Kannada colloquial nicknames:

  1. KANNADA SCRIPT MAPPING — the same name clusters in alias_resolver
     also written in actual Kannada Unicode (ಮಂಜು, ಮಂಜುನಾಥ, ...), so a
     voice-transcribed or natively-typed Kannada query resolves to the
     same person as a Roman-script query.

  2. CROSS-COMMUNITY TRANSLITERATION VARIANTS — Indian police records
     are full of spelling variance that has nothing to do with
     nicknames: the same name transliterated differently by different
     clerks (Mohammed / Mohammad / Muhammad / Md / Mohd, Anthony /
     Antony, etc). Treating this as a separate mechanism from "nickname
     resolution" matters: these aren't colloquial shortenings, they're
     spelling-convention variance, and conflating the two would produce
     wrong reasoning explanations in the audit trail.

HONESTY NOTE: the Kannada-script list below covers common, well-known
names with reasonable confidence. It is explicitly a starter set —
before relying on it for a real deployment, have a native Kannada
speaker on the team review and extend it. Same standard applies to any
language glossary regardless of who wrote it.
"""
import re

# Kannada Unicode block: U+0C80 to U+0CFF
_KANNADA_RANGE = re.compile(r'[\u0C80-\u0CFF]')


def contains_kannada_script(text: str) -> bool:
    return bool(_KANNADA_RANGE.search(text))


# canonical Roman key (must match a key or alias in alias_resolver.KANNADA_NAME_ALIASES)
# -> list of Kannada-script spellings
KANNADA_SCRIPT_ALIASES = {
    "manjunath": ["ಮಂಜುನಾಥ್", "ಮಂಜುನಾಥ"],
    "manju":     ["ಮಂಜು"],
    "manja":     ["ಮಂಜ"],
    "ramesh":    ["ರಮೇಶ್", "ರಮೇಶ"],
    "ramu":      ["ರಾಮು"],
    "rama":      ["ರಾಮ"],
    "krishna":   ["ಕೃಷ್ಣ"],
    "krishnamurthy": ["ಕೃಷ್ಣಮೂರ್ತಿ"],
    "shiva":     ["ಶಿವ"],
    "shivakumar":["ಶಿವಕುಮಾರ್"],
    "suresh":    ["ಸುರೇಶ್", "ಸುರೇಶ"],
    "nagaraj":   ["ನಾಗರಾಜ್", "ನಾಗರಾಜ"],
    "gowda":     ["ಗೌಡ"],
    "basavaraj": ["ಬಸವರಾಜ್", "ಬಸವರಾಜ"],
    "venkatesh": ["ವೆಂಕಟೇಶ್", "ವೆಂಕಟೇಶ"],
    "lakshmi":   ["ಲಕ್ಷ್ಮಿ"],
    "mohammed":  ["ಮೊಹಮ್ಮದ್"],
    "puttaswamy":["ಪುಟ್ಟಸ್ವಾಮಿ"],
    "chandrashekar": ["ಚಂದ್ರಶೇಖರ್"],
}

# Reverse map: kannada-script string -> canonical roman key
_SCRIPT_TO_CANONICAL = {}
for _canon, _scripts in KANNADA_SCRIPT_ALIASES.items():
    for _s in _scripts:
        _SCRIPT_TO_CANONICAL[_s] = _canon


def transliterate_to_roman_key(text: str):
    """Best-effort: if the text is a known Kannada-script name, return
    its canonical Roman resolution key. Returns None if unrecognised —
    callers should fall back to Ollama (if available) or flag for
    manual translation rather than guess."""
    t = text.strip()
    return _SCRIPT_TO_CANONICAL.get(t)


# Cross-community transliteration variants — spelling convention
# variance, NOT colloquial nicknames. Kept as its own dictionary so the
# resolution engine can label WHY two spellings matched correctly.
TRANSLITERATION_VARIANTS = {
    "mohammed": ["mohammad", "muhammad", "muhammed", "md", "mohd", "mohammod", "mahammad"],
    "abdul":    ["abdhul", "abdool"],
    "ibrahim":  ["ebrahim", "ibraheem"],
    "yusuf":    ["yousuf", "yousif", "usuf"],
    "anthony":  ["antony", "anthonisamy", "antonisamy"],
    "joseph":   ["jospeh", "joesph", "josef"],
    "mathew":   ["mathews", "matthew", "mathai"],
    "thomas":   ["thoma", "thommen"],
    "d'souza":  ["dsouza", "de souza"],
}
_VARIANT_TO_CANONICAL = {}
for _canon, _variants in TRANSLITERATION_VARIANTS.items():
    for _v in _variants:
        _VARIANT_TO_CANONICAL[_v.lower()] = _canon
    _VARIANT_TO_CANONICAL[_canon.lower()] = _canon


def resolve_transliteration(term: str):
    """Returns the canonical spelling-cluster key for a term, or None."""
    return _VARIANT_TO_CANONICAL.get(term.lower().strip())
