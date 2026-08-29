"""
KAVACH Brain — Indian Name & Alias Resolution Engine
======================================================
100% self-contained. Zero external API calls. Zero paid model dependency.

Solves a real, common problem in Indian policing: the same person appears
under different name spellings across different FIRs — a formal name in
one, a street/colloquial name in another, a transliteration variant in a
third. An investigator searching "Manja" should still find "Manjunath
Gowda" if that's who they mean.

THREE CASCADING RESOLUTION STRATEGIES
--------------------------------------
1. Curated alias dictionary   — known nickname <-> formal-name mappings
                                  (fast, high-confidence, human-curated)
2. Phonetic key matching      — collapses Kannada transliteration variance
                                  (trailing vowel swaps: manju/manja/manji,
                                   consonant substitution: sh<->s, v<->w)
3. Fuzzy string similarity    — catches close spelling variants nothing
                                  else caught (edit-distance based)

Every match returned includes a plain-language `reason` — this is what
lets KAVACH show its work instead of being a black box (Explainable AI
requirement).

NOTE ON THE ALIAS DICTIONARY: this is a starter set covering common
Karnataka naming patterns. It is intentionally a plain Python dict, not
buried inside logic, so any team member — especially a Kannada speaker —
can extend it in thirty seconds without touching resolution code.
"""
import difflib
import re

from . import transliteration

# canonical formal name -> [common nicknames / colloquial variants]
KANNADA_NAME_ALIASES = {
    "manjunath":       ["manju", "manja", "manji", "manjappa", "manjesh"],
    "krishnamurthy":   ["krishna", "kittu", "kitty", "murthy", "krishnappa"],
    "krishna":         ["kittu", "kitty", "krishnappa"],
    "basavaraj":       ["basu", "basya", "basava", "basanna", "basavanna"],
    "venkatesh":       ["venky", "venka", "venkat", "venki"],
    "venkataramana":   ["venkat", "rama", "venki"],
    "venkataramu":     ["venkat", "ramu"],
    "nagaraj":         ["naga", "nagesh", "nagappa", "nagu"],
    "nagaraja":        ["naga", "nagesh", "nagappa", "nagu"],
    "siddaraju":       ["siddu", "siddappa", "siddaraj", "sidda"],
    "siddalingappa":   ["siddu", "lingappa", "siddesh"],
    "chandrashekar":   ["chandru", "shekar", "chandu", "chandra"],
    "chandrashekhar":  ["chandru", "shekar", "chandu", "chandra"],
    "puttaswamy":      ["puttu", "puttaraju", "puttegowda"],
    "shivakumar":      ["shivu", "shiva", "shivanna"],
    "shivanna":        ["shivu", "shiva"],
    "shivappa":        ["shivu", "shiva"],
    "lakshmi":         ["lucky", "laxmi", "lakshmamma", "lachi"],
    "govindaraju":     ["govinda", "govind", "govindappa"],
    "ramachandra":     ["ramu", "ramesh", "chandra", "ram"],
    "ramakrishna":     ["ramu", "ramesh", "krishna", "ram"],
    "narasimhamurthy": ["narsi", "murthy", "simha"],
    "gangadhar":       ["ganga", "gangappa", "gangu"],
    "mahadevappa":     ["mahadev", "maha", "devappa"],
    "mahadeva":        ["mahadev", "maha"],
    "yellappa":        ["yella", "yellu"],
    "honnappa":        ["honna", "honnu"],
    "puttamma":        ["puttu", "putti"],
    "kariyappa":       ["kariya", "kari"],
    "srinivasa":       ["srinu", "seenu", "srini", "vasu"],
    "srinivasan":      ["srinu", "seenu", "srini"],
    "prabhakar":       ["prabhu", "pabbu"],
    "raghavendra":     ["raghu", "raghava"],
    "gurumurthy":      ["guru", "murthy"],
    "hanumantharaya":  ["hanuma", "hanumanth", "raya"],
    "veeranna":        ["veera", "veeru"],
    "veerabhadrappa":  ["veera", "veeru", "bhadra"],
    "somashekar":      ["soma", "shekar", "somu"],
    "rangaswamy":      ["ranga", "rangappa"],
    "channabasappa":   ["channa", "basappa", "channu"],
    "eregowda":        ["ere", "eregowda"],
    "puttegowda":      ["puttu", "gowda"],
    "byrappa":         ["byra", "byru"],
    "dyamappa":        ["dyava", "dyavu"],
    "renukappa":       ["renuka", "renu"],
    "parvathamma":     ["parvathi", "parvathi amma"],
}

# Reverse lookup built once at import time: alias(lower) -> canonical
_ALIAS_TO_CANONICAL = {}
for _canon, _aliases in KANNADA_NAME_ALIASES.items():
    for _a in _aliases:
        _ALIAS_TO_CANONICAL[_a.lower()] = _canon
    _ALIAS_TO_CANONICAL[_canon.lower()] = _canon


_VOWELS = "aeiou"
_CONSONANT_SUBS = [
    ("sh", "s"), ("ph", "f"), ("dh", "d"), ("th", "t"),
    ("v", "w"), ("kh", "k"), ("gh", "g"), ("bh", "b"),
]


def phonetic_key(token: str) -> str:
    """
    Coarse phonetic key collapsing common Kannada transliteration variance.
    manju / manja / manji all reduce to "manj" — because Kannada colloquial
    speech frequently swaps the trailing vowel of a name (u/a/i) while the
    root stays fixed. This single normalisation is what lets a plain
    substring/dictionary search catch nickname spelling variance that no
    dictionary entry was written for.
    """
    t = token.lower().strip()
    t = re.sub(r'[^a-z]', '', t)
    if not t:
        return ""
    for a, b in _CONSONANT_SUBS:
        t = t.replace(a, b)
    t = re.sub(r'(.)\1+', r'\1', t)          # collapse doubled letters
    if t and t[-1] in _VOWELS:                # strip ONE trailing vowel
        t = t[:-1]
    return t


def _first_token(name: str) -> str:
    name = (name or "").strip()
    return name.split()[0] if name else ""


def _record(seen, name, confidence, reason, method):
    if name not in seen or seen[name]["confidence"] < confidence:
        seen[name] = {"name": name, "confidence": confidence, "reason": reason, "method": method}


def resolve_name(query_name: str, known_names: list, min_fuzzy: float = 0.72) -> list:
    """
    Given a name/nickname as typed by an investigator, and the list of
    full names actually present in the database, return ranked candidate
    matches — each with a plain-language reason for the match.

    Returns: [{"name","confidence","reason","method"}, ...] sorted desc.
    """
    # If the query arrived in Kannada script, resolve it to a Roman key first
    if transliteration.contains_kannada_script(query_name):
        script_key = transliteration.transliterate_to_roman_key(query_name.strip())
        q_first = (script_key or query_name).lower()
    else:
        q_first = _first_token(query_name).lower()

    if not q_first:
        return []
    q_canonical = _ALIAS_TO_CANONICAL.get(q_first, q_first)
    q_translit = transliteration.resolve_transliteration(q_first)
    q_key = phonetic_key(q_first)

    seen = {}
    for full_name in known_names:
        if transliteration.contains_kannada_script(full_name):
            script_key = transliteration.transliterate_to_roman_key(full_name.strip())
            n_first = (script_key or full_name).lower()
        else:
            n_first = _first_token(full_name).lower()
        if not n_first:
            continue

        # 1. Exact match — full string identical is always exact. A shared
        # FIRST token alone is NOT enough on its own: common first names
        # (Ganesh, Ramesh, ...) would otherwise wrongly merge two different
        # people. Only treat first-token equality as "exact" when surnames
        # also agree, or when one side genuinely has no surname to compare.
        full_match = query_name.strip().lower() == full_name.strip().lower()
        if full_match:
            _record(seen, full_name, 1.0, "Exact name match", "exact")
            continue
        if q_first == n_first:
            q_tokens, n_tokens = query_name.strip().lower().split(), full_name.strip().lower().split()
            q_surname = q_tokens[-1] if len(q_tokens) > 1 else None
            n_surname = n_tokens[-1] if len(n_tokens) > 1 else None
            if q_surname is None or n_surname is None:
                _record(seen, full_name, 0.85,
                        "First name matches; no surname available on one side to confirm", "exact")
                continue
            if q_surname == n_surname:
                _record(seen, full_name, 1.0, "Exact name match", "exact")
                continue
            # same first name, DIFFERENT surname — likely two different
            # people (e.g. "Ganesh Bhat" vs "Ganesh Patel"). Do not treat
            # as exact; fall through to the weaker methods below, which
            # correctly will not match either.
            continue

        # 2. Alias dictionary — both terms map to the same canonical formal name
        n_canonical = _ALIAS_TO_CANONICAL.get(n_first, n_first)
        if q_canonical == n_canonical:
            _record(
                seen, full_name, 0.90,
                f'Known alias — "{query_name}" is commonly used for names like '
                f'"{full_name.split()[0]}" (both resolve to "{q_canonical.title()}")',
                "alias_dictionary",
            )
            continue

        # 3. Cross-community transliteration variant (spelling convention,
        #    not a nickname — e.g. Mohammed / Mohd / Muhammad)
        n_translit = transliteration.resolve_transliteration(n_first)
        if q_translit and q_translit == n_translit:
            _record(
                seen, full_name, 0.88,
                f'Transliteration variant — "{query_name}" and "{full_name.split()[0]}" '
                f'are common alternate spellings of the same name',
                "transliteration_variant",
            )
            continue

        # 4. Phonetic key — Kannada trailing-vowel / consonant variant
        n_key = phonetic_key(n_first)
        if q_key and q_key == n_key:
            _record(
                seen, full_name, 0.78,
                f'Phonetic match — "{query_name}" and "{full_name.split()[0]}" share '
                f'the same root sound (likely transliteration variant)',
                "phonetic",
            )
            continue

        # 5. Fuzzy string similarity — catch-all for close spellings
        sim = difflib.SequenceMatcher(None, q_first, n_first).ratio()
        if sim >= min_fuzzy:
            _record(
                seen, full_name, round(sim, 2),
                f'Fuzzy spelling match ({int(sim * 100)}% character similarity)',
                "fuzzy",
            )

    return sorted(seen.values(), key=lambda r: -r["confidence"])


def expand_query_terms(query_name: str) -> list:
    """
    Given a typed name, return dictionary-known variant spellings —
    useful for building a direct SQL LIKE-based search without needing
    the full known_names list on hand.
    """
    q_first = _first_token(query_name).lower()
    canonical = _ALIAS_TO_CANONICAL.get(q_first, q_first)
    variants = {q_first, canonical}
    variants.update(KANNADA_NAME_ALIASES.get(canonical, []))
    return sorted(variants)


def cluster_identities(raw_people: list, age_tolerance: int = 3) -> list:
    """
    Given a flat list of raw per-case person records — each a dict with
    at least {"ref_id", "name", "age", "district"} — cluster records that
    likely refer to the SAME real individual, using alias/phonetic/fuzzy
    matching plus an age-and-district sanity check (protects against
    false positives: two different 45-year-olds both named "Manju" in
    different districts should NOT be merged).

    Returns a list of clusters:
      [{"members": [ref_id, ...], "canonical_name": str,
        "match_reasons": [...] }, ...]

    This is what powers KAVACH's cross-FIR identity resolution: it is run
    once during data ingestion (see seed_data.py) and its output is what
    an investigator sees as a single "person profile" spanning multiple
    FIRs, even when each FIR spelled the name differently.
    """
    unclustered = list(raw_people)
    clusters = []

    while unclustered:
        seed = unclustered.pop(0)
        cluster = {
            "members": [seed["ref_id"]],
            "canonical_name": seed["name"],
            "match_reasons": [],
        }
        remaining = []
        for candidate in unclustered:
            same_district = candidate.get("district") == seed.get("district")
            age_ok = (
                candidate.get("age") is not None and seed.get("age") is not None and
                abs(candidate["age"] - seed["age"]) <= age_tolerance
            )
            if not (same_district and age_ok):
                remaining.append(candidate)
                continue

            matches = resolve_name(candidate["name"], [seed["name"]])
            if matches and matches[0]["confidence"] >= 0.78:
                cluster["members"].append(candidate["ref_id"])
                cluster["match_reasons"].append({
                    "matched_name": candidate["name"],
                    "against": seed["name"],
                    **{k: v for k, v in matches[0].items() if k != "name"},
                })
                # prefer the longer / more "formal-looking" name as canonical
                if len(candidate["name"]) > len(cluster["canonical_name"]):
                    cluster["canonical_name"] = candidate["name"]
            else:
                remaining.append(candidate)
        unclustered = remaining
        clusters.append(cluster)

    return clusters
