"""
KAVACH Brain — Bounded General-Knowledge Fallback
======================================================
Everywhere else in this system, an answer is only ever as good as a row
in the database — that's the whole zero-hallucination promise. This
module is the one deliberate, narrow exception, and it's designed to
NEVER blur into the rest of the system's guarantee.

When the deterministic router genuinely can't classify what the officer
is asking (not "no matching records" — that's a real, honest answer
already handled elsewhere — but "this isn't a database question at
all"), the old behaviour was a dead-end clarification prompt even for
things like "what is a charge sheet?" or "what can I ask you?". That's
a bad experience for a question that has a perfectly good, stable
answer that doesn't depend on the case data at all.

This module answers ONLY from a small, hand-written, curated table
below — never from the LLM's own general knowledge, and never from the
live database. Nothing here is looked up dynamically. If Ollama is
running, brain.py may ask it to smooth the PHRASING of the matched
entry (same polish_response() used elsewhere) — but the facts
themselves always come from this file, and every response is labelled
"General guidance — not case-specific" so it can never be mistaken for
a grounded query result.

SOURCES / ACCURACY NOTE
  The IPC -> BNS section mapping below reflects the Bharatiya Nyaya
  Sanhita, 2023, which replaced the IPC with effect from 1 July 2024.
  Only the handful of sections this project's own seed data actually
  uses (seed_data.py's SECTIONS table) are included, cross-checked
  against multiple legal-reference sources. This is reference
  information for an officer's convenience, not legal advice — the
  date an offence occurred decides which code applies (on/after
  1 July 2024 -> BNS; before -> IPC continues to apply to that case),
  and the authoritative source is always the bare act, not this table.
"""

# ── Procedural / terminology glossary ────────────────────────────────
GLOSSARY = {
    "fir": (
        "An FIR (First Information Report) is the written record a police station makes the moment it "
        "receives information about a cognizable offence — it's what starts a criminal investigation "
        "under Indian procedure. It has to be registered without unnecessary delay once a cognizable "
        "offence is reported."
    ),
    "charge sheet": (
        "A charge sheet (also called a chargesheet or final report) is the document an Investigating "
        "Officer files in court once investigation is complete — it lays out the evidence gathered and "
        "names the accused to be tried. Filing it is what moves a case from 'under investigation' to "
        "the trial stage."
    ),
    "chargesheet": None,  # alias, filled below
    "cognizable offence": (
        "A cognizable offence is one serious enough that police can register an FIR and start "
        "investigating — including arrest — without needing a magistrate's prior permission. Murder, "
        "robbery and rape are examples. Non-cognizable offences need a magistrate's order first."
    ),
    "non-cognizable offence": (
        "A non-cognizable offence is one where police can't investigate or arrest without a magistrate's "
        "prior order — generally less serious offences than cognizable ones."
    ),
    "bail": (
        "Bail is release of an accused person from custody, usually on a bond or surety, pending trial "
        "or further proceedings — it isn't an acquittal, just a release condition."
    ),
    "anticipatory bail": (
        "Anticipatory bail is bail sought BEFORE arrest, when someone has reason to believe they may be "
        "arrested for a non-bailable offence — it's a protective order against arrest, granted by a "
        "Sessions or High Court."
    ),
    "remand": (
        "Remand is a magistrate sending an arrested person into custody (police or judicial) for a "
        "defined period while investigation continues, instead of releasing them."
    ),
    "io": (
        "IO stands for Investigating Officer — the officer formally assigned to investigate a "
        "registered case, respond to it, gather evidence, and ultimately file the charge sheet."
    ),
    "undertrial": (
        "An undertrial is an accused person who has been charged and is in judicial custody awaiting or "
        "during trial — not yet convicted or acquitted."
    ),
    "mo": (
        "MO (modus operandi) is the characteristic pattern or method an offender tends to use — KAVACH "
        "uses recorded MO text for the case-similarity feature (ask 'find similar cases to <FIR>')."
    ),
}
GLOSSARY["chargesheet"] = GLOSSARY["charge sheet"]

# ── IPC -> BNS section reference, limited to sections this project's own
#    seed data (seed_data.py SECTIONS) actually uses — see accuracy note
#    above. Format: crime label -> (ipc_section, bns_section, note) ─────
SECTION_REFERENCE = {
    "murder":            ("302", "103",     None),
    "attempt to murder": ("307", "109",     None),
    "theft":             ("379", "303(2)",  None),
    "vehicle theft":     ("379", "303(2)",  "same section as general theft"),
    "robbery":           ("392", "309(4)",  None),
    "dacoity":           ("395", "310(2)",  None),
    "assault":           ("324", "118",     "voluntarily causing hurt by dangerous weapons/means"),
    "house-breaking":    ("454", "331",     None),
    "burglary":          ("454", "331",     "house-breaking"),
    "fraud":             ("420", "318",     "cheating"),
    "cheating":          ("420", "318",     None),
    "rape":              ("376", "64",      None),
    "domestic violence": ("498a", "85",     "cruelty by husband or his relatives"),
}

_BNS_NOTE = (
    "The Bharatiya Nyaya Sanhita (BNS) replaced the IPC from 1 July 2024. Which one applies to a "
    "specific case depends on the date of the offence, not the date you're asking — offences before "
    "1 July 2024 continue under the IPC; the BNS section is the one that applies going forward. Treat "
    "this as a quick reference, not a substitute for the bare act."
)

# ── KAVACH's own capabilities — for "what can you ask me / what can you do" ──
CAPABILITIES_TEXT = (
    "You can ask me about people, cases, or patterns in the crime data — for example: a person's name "
    "or alias to pull their profile; \"pending cases in <district>\"; \"repeat offenders with 3+ "
    "convictions\"; \"gang-affiliated identities\"; \"<person>'s network\" for their known connections; "
    "\"predict <crime type> in <district> next month\" for a trend forecast; \"cases similar to <FIR "
    "number>\"; or an 18-digit FIR/Crime Number directly for an exact lookup. Everything I answer about "
    "cases or people comes straight from the database — I'll say so plainly when nothing matches, "
    "rather than guess."
)


def _normalise(text: str) -> str:
    return " ".join(text.lower().strip().split())


def match(message: str):
    """
    Returns (answer_text, topic_label) if `message` matches something in
    the curated table above, else (None, None). Deliberately simple,
    deliberately bounded — this is a lookup, not a classifier.

    Every match below uses \\b word-boundary regex, never a bare
    substring check — short entries like "mo" or "io" would otherwise
    match inside completely ordinary words ("mo" inside "more", "io"
    inside "portfolio"), and "fir" would match inside "first" or
    "confirm". A live test caught exactly this before it shipped.
    """
    import re
    text = _normalise(message)

    def has_word(term: str) -> bool:
        return re.search(r'\b' + re.escape(term) + r'\b', text) is not None

    # "what can you do / ask me / help with" — capability question
    if any(p in text for p in ("what can you do", "what can i ask", "what can you ask",
                                 "what can you help", "what all can you", "how do i use you",
                                 "help me use", "how can you help", "what are you capable")):
        return CAPABILITIES_TEXT, "KAVACH capabilities"

    # A bare or "section <n>" style number, or "ipc <n>" / "bns <n>"
    sec_match = re.search(r'\b(?:ipc|bns|section)\s*(\d+[a-z]?)\b', text)
    if sec_match:
        code = sec_match.group(1)
        for label, (ipc, bns, note) in SECTION_REFERENCE.items():
            if code == ipc.lower() or code == bns.lower().split("(")[0]:
                extra = f" ({note})" if note else ""
                answer = (f'IPC Section {ipc} corresponds to {label.title()}{extra}, which is BNS '
                           f'Section {bns} under the current code. {_BNS_NOTE}')
                return answer, f"IPC/BNS section {code}"

    # Crime-type name asked directly ("what section is theft under")
    for label, (ipc, bns, note) in SECTION_REFERENCE.items():
        if has_word(label) and ("section" in text or "ipc" in text or "bns" in text or "under what" in text):
            extra = f" ({note})" if note else ""
            answer = (f'{label.title()} is IPC Section {ipc}{extra} — BNS Section {bns} under the '
                       f'current code. {_BNS_NOTE}')
            return answer, f"{label} section reference"

    # Procedural glossary terms — longest term first, so "anticipatory bail"
    # matches before the shorter "bail" it contains; word-boundary match
    # so multi-word terms ("charge sheet") and short ones ("io", "mo",
    # "fir") never fire on a substring of an unrelated word.
    for term in sorted(GLOSSARY, key=len, reverse=True):
        definition = GLOSSARY[term]
        if term and definition and has_word(term):
            return definition, f'definition of "{term}"'

    return None, None
