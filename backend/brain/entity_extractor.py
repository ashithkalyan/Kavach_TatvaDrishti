"""
KAVACH Brain — Crime-Domain Entity Extraction
=================================================
Rule-based extraction, tuned to the Karnataka crime domain rather than
attempting generic open-world NER (which needs training data we don't
have and can't honestly claim). Person names are resolved via a
closed-world scan against the actual database + the alias dictionary,
which is far more reliable than generic NER for this bounded task.

LANGUAGE COVERAGE — read this before assuming full Kannada fluency:
  Tier 1 (always on):    English + "Kanglish" (Kannada words typed in
                          Roman script) domain vocabulary — this is how
                          most Indian users actually type on phones.
  Tier 2 (optional):     A modest, clearly-labelled Kannada-script
                          glossary for the most common crime terms.
                          Extend this with a native speaker's input —
                          it is intentionally a plain dict, not logic.
  Tier 3 (optional, if
  Ollama is running):    Full free-form multilingual understanding via
                          a local open-weight LLM — see ollama_client.py.
"""
import re
from datetime import datetime

from . import alias_resolver

# canonical CrimeSubHead label -> trigger terms (English + Kanglish + a
# small starter Kannada-script glossary)
CRIME_TERM_MAP = {
    "Murder":              ["murder", "murdered", "killed", "killing", "homicide"],
    "Attempt to Murder":   ["attempt to murder", "attempted murder", "tried to kill"],
    "Dacoity":             ["dacoity", "armed gang robbery"],
    "Robbery":             ["robbery", "robbed", "held up"],
    "Kidnapping":          ["kidnap", "kidnapping", "abduction", "abducted"],
    "Rape":                ["rape", "sexual assault"],
    "Assault":             ["assault", "beaten", "attacked", "hit with"],
    "Burglary":            ["burglary", "break-in", "broke into", "house broken"],
    "Chain Snatching":     ["chain snatching", "chain snatched", "gold chain"],
    "Vehicle Theft":       ["vehicle theft", "bike theft", "car theft", "two-wheeler stolen", "vehicle stolen"],
    "Theft":               ["theft", "stolen", "stealing", "steal", "chori"],
    "Fraud":               ["fraud", "cheated", "cheating", "duped", "scam", "chit fund"],
    "Drug Offense":        ["drug", "narcotics", "ndps", "ganja", "peddling", "smuggling", "contraband"],
    "Cybercrime":          ["cyber", "online fraud", "upi fraud", "otp fraud", "phishing", "hacking", "digital arrest"],
    "Domestic Violence":   ["domestic violence", "dowry", "498a", "harassment by husband"],
    # starter Kannada-script glossary — extend with native review
    "Theft ":              ["ಕಳ್ಳತನ"],
    "Murder ":             ["ಕೊಲೆ"],
    "Robbery ":            ["ದರೋಡೆ"],
}
# normalise the trailing-space duplicate keys back into their real labels
_KN_MAP_FIX = {"Theft ": "Theft", "Murder ": "Murder", "Robbery ": "Robbery"}
for _bad, _good in _KN_MAP_FIX.items():
    CRIME_TERM_MAP[_good] = CRIME_TERM_MAP.get(_good, []) + CRIME_TERM_MAP.pop(_bad)

DISTRICT_ALIASES = {
    "Bengaluru Urban":    ["bengaluru", "bangalore", "blr", "bengaluru urban", "bangalore urban"],
    "Bengaluru Rural":    ["bengaluru rural", "bangalore rural"],
    "Mysuru":             ["mysuru", "mysore"],
    "Hubballi-Dharwad":   ["hubballi", "dharwad", "hubli"],
    "Mangaluru":          ["mangaluru", "mangalore", "dakshina kannada"],
    "Belagavi":           ["belagavi", "belgaum"],
    "Kalaburagi":         ["kalaburagi", "gulbarga"],
    "Davanagere":         ["davanagere", "davangere"],
    "Shivamogga":         ["shivamogga", "shimoga"],
    "Tumakuru":           ["tumakuru", "tumkur"],
    "Vijayapura":         ["vijayapura", "bijapur"],
    "Ballari":            ["ballari", "bellary"],
}

_RELATIVE_DATE_PATTERNS = [
    (r'last (\d+) months?',  lambda m: _months_ago(int(m.group(1)))),
    (r'last (\d+) years?',   lambda m: _years_ago(int(m.group(1)))),
    (r'\blast month\b',      lambda m: _months_ago(1)),
    (r'\bthis year\b',       lambda m: datetime(datetime.now().year, 1, 1)),
    (r'\blast year\b',       lambda m: datetime(datetime.now().year - 1, 1, 1)),
    (r'\b(20\d{2})\b',       lambda m: datetime(int(m.group(1)), 1, 1)),
]


def _months_ago(n):
    d = datetime.now()
    m, y = d.month - n, d.year
    while m <= 0:
        m += 12
        y -= 1
    return datetime(y, m, 1)


def _years_ago(n):
    return datetime(datetime.now().year - n, 1, 1)


def extract_crime_types(text: str) -> list:
    t = text.lower()
    return [canon for canon, terms in CRIME_TERM_MAP.items() if any(term in t for term in terms)]


def extract_districts(text: str) -> list:
    t = text.lower()
    return [canon for canon, terms in DISTRICT_ALIASES.items() if any(term in t for term in terms)]


def extract_date_from(text: str):
    t = text.lower()
    for pattern, fn in _RELATIVE_DATE_PATTERNS:
        m = re.search(pattern, t)
        if m:
            return fn(m).strftime("%Y-%m-%d")
    return None


def extract_numeric_threshold(text: str):
    """'3+ convictions' / 'more than 5' / 'at least 2' -> (operator, value)"""
    t = text.lower()
    m = re.search(r'(\d+)\s*\+', t)
    if m:
        return (">=", int(m.group(1)))
    m = re.search(r'more than (\d+)', t)
    if m:
        return (">", int(m.group(1)))
    m = re.search(r'at least (\d+)', t)
    if m:
        return (">=", int(m.group(1)))
    m = re.search(r'exactly (\d+)', t)
    if m:
        return ("=", int(m.group(1)))
    return None


def extract_person_name_candidates(text: str) -> list:
    """
    Closed-world name-candidate scan: capitalised words in the query,
    plus any known alias-dictionary term appearing as a standalone word
    (so lowercase nicknames like 'manja' are caught even without
    capitalisation).

    Consecutive capitalised words ("Basavaraj Rao") are ALSO captured as
    one joined candidate, in addition to the individual words. Without
    this, a full name is only ever offered to alias_resolver.resolve_name()
    one word at a time — so a person searched for by their exact full
    name never gets the chance to hit the 1.0-confidence exact-match
    branch, and instead only scores the weaker "first name matches, no
    surname to confirm" (0.85) result, which can rank BELOW an unrelated
    person matched purely through the nickname/alias dictionary (0.90).
    Offering the joined full name too lets the real exact match win, the
    way an investigator typing a complete name would expect.
    """
    t_lower = text.lower()
    candidates = set()

    for w in re.findall(r"[A-Za-z]+", text):
        if len(w) >= 3 and w[0].isupper() and w.lower() not in _COMMON_CAPS_NOISE:
            candidates.add(w)

    for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text):
        phrase = m.group(0)
        if phrase.split()[0].lower() not in _COMMON_CAPS_NOISE:
            candidates.add(phrase)

    for canon, aliases in alias_resolver.KANNADA_NAME_ALIASES.items():
        for term in aliases + [canon]:
            if re.search(rf'\b{re.escape(term)}\b', t_lower):
                candidates.add(term)

    return sorted(candidates)


_COMMON_CAPS_NOISE = {
    "show", "list", "find", "who", "which", "kavach", "fir", "ksp",
    "district", "bengaluru", "mysuru", "murder", "theft", "robbery",
    "tell", "give", "ask", "get", "please", "know", "about", "info",
    "information", "details", "search", "does", "any", "there",
}

# Extra conversational words that should NEVER be treated as an attempted
# name search even when they're the only word in the message — see the
# single-word fallback in extract() below.
_CONVERSATIONAL_NOISE = _COMMON_CAPS_NOISE | {
    "hi", "hello", "hey", "thanks", "thank", "ok", "okay", "yes", "no",
    "sure", "bye", "test", "hmm", "yo",
}


_FIR_NUMBER_PATTERN = re.compile(r'\b\d{18}\b')
# Tolerant match used first (see extract_fir_number_candidate()'s
# docstring for why): a run of digits allowing internal spaces/hyphens,
# matched against the ORIGINAL text so real word boundaries around
# natural-language phrasing stay intact.
_FIR_NUMBER_LOOSE_PATTERN = re.compile(r'\b\d[\d\s-]{16,40}\d\b')


def extract_fir_number_candidate(text: str):
    """
    An 18-digit FIR/Crime Number (see the schema doc: 1-digit category +
    4-digit district + 4-digit station + 4-digit year + 5-digit serial)
    is the single most unambiguous thing an officer can type — if one is
    present, brain.py short-circuits straight to an exact-match lookup
    rather than routing through intent classification, so a pasted FIR
    number is never mistaken for an unclear query needing clarification.

    BUG FIX: this used to strip every space/hyphen from the WHOLE
    message before matching \\b\\d{18}\\b — meant to tolerate an officer
    formatting the number with internal spacing ("1001 0004 7202 1000
    01"), but it also collapsed ordinary prose around the number (e.g.
    "brief me on 100100047202100001" -> "briefmeon100100047202100001"),
    which silently broke the \\b boundary check right where it mattered:
    a letter and a digit are both "word" characters, so there is no
    boundary between them once the space is gone. Any natural-language
    phrasing that put an FIR number at the end of a sentence with no
    trailing punctuation before it was silently failing to extract at
    all. Fixed by matching a tolerant digit-and-separator run against
    the ORIGINAL text first (so real word boundaries around prose stay
    intact), then stripping separators only from within that
    already-isolated match and checking the result is exactly 18 digits.
    """
    for m in _FIR_NUMBER_LOOSE_PATTERN.finditer(text):
        digits_only = re.sub(r'[\s-]', '', m.group(0))
        if len(digits_only) == 18:
            return digits_only
    return None


def extract(text: str) -> dict:
    crime_types = extract_crime_types(text)
    districts = extract_districts(text)
    date_from = extract_date_from(text)
    threshold = extract_numeric_threshold(text)
    person_name_candidates = extract_person_name_candidates(text)
    fir_number_candidate = extract_fir_number_candidate(text)

    # BUG FIX: a capitalised word that is itself part of an
    # already-matched district name ("Urban" inside "Bengaluru Urban",
    # "Rural" inside "Bengaluru Rural", "Dharwad" inside
    # "Hubballi-Dharwad") was being picked up by
    # extract_person_name_candidates() above as ITS OWN separate name
    # candidate — extract_person_name_candidates() only sees raw text,
    # it has no idea "Urban" was already accounted for as part of a
    # district. Downstream this silently turned an ordinary district
    # query into a person-scoped search for a person named "Urban"
    # (who doesn't exist), returning zero rows for what should have been
    # an ordinary, successful district/crime-type search — see
    # sql_builder.build()'s name_terms fix for the other half of this.
    if districts and person_name_candidates:
        district_words = set()
        for d in districts:
            district_words.update(w.lower() for w in re.findall(r"[A-Za-z]+", d))
        person_name_candidates = [c for c in person_name_candidates if c.lower() not in district_words]

    # Last-resort single-word fallback: extract_person_name_candidates()
    # above only catches CAPITALISED words (or a known alias), so a name
    # typed in lowercase — very common on a phone keyboard or via
    # voice-to-text — was previously invisible to every downstream
    # signal. That meant a message like "ashith" (a real attempted name
    # search) or "fjsfsfsjf" (gibberish) both produced ZERO extracted
    # entities and fell all the way through to the unconditional "most
    # recent 30 records" fallback in sql_builder.py, which
    # response_generator.py then reported as if those 30 unrelated rows
    # had answered the question — a real bug, reported directly against
    # this app (typing a random string, or a real name that just isn't
    # in the database, both produced a confident "Found 30 records").
    #
    # Treating a genuinely LONE (single-word), otherwise-unclassified
    # word as an attempted name search means it gets a REAL person_lookup
    # query and an honest "no person named X found" when nothing
    # matches — never a fabricated-looking match, and never an
    # unnecessary clarification prompt for what was clearly already a
    # specific, if unproductive, query attempt. Deliberately scoped to
    # exactly one word: a multi-word sentence that matches nothing is a
    # message the clarification gate in brain.py should handle instead
    # (see _needs_clarification()) — guessing that EVERY unmatched word
    # in a longer sentence is a surname would be far too aggressive.
    if not (crime_types or districts or date_from or threshold or person_name_candidates or fir_number_candidate):
        words = re.findall(r"[A-Za-z]+", text)
        if len(words) == 1 and len(words[0]) >= 3 and words[0].lower() not in _CONVERSATIONAL_NOISE:
            person_name_candidates = [words[0]]

    return {
        "crime_types":              crime_types,
        "districts":               districts,
        "date_from":                date_from,
        "threshold":                threshold,
        "person_name_candidates":  person_name_candidates,
        "fir_number_candidate":    fir_number_candidate,
    }
