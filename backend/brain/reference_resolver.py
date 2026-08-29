"""
KAVACH Brain — In-Session Reference Resolution
==================================================
Closes a real gap: before this module, "Tell me about Basavaraj Rao"
followed by "does he have any pending cases?" silently dropped "he" —
entity_extractor.py has no concept of pronouns, so the second query ran
with zero person filter and quietly returned recent cases for
EVERYONE, not Basavaraj Rao. That's worse than an error, because
nothing in the response says the reference was lost.

WHAT THIS MODULE DOES
  Scans the officer's raw message for a small, deliberately bounded set
  of reference patterns — pronouns ("he"/"she"/"they"/"his"/"her"),
  gang references ("that gang"/"the syndicate"), and ordinal references
  ("the second one"/"the first result") — and substitutes in whatever
  the working context / last turn actually resolved to. If it can
  substitute something, it injects it into `entities` exactly the way
  a typed name would have arrived, so every downstream stage (alias
  resolution, SQL building, response generation) behaves identically
  to the officer having typed the full name out again.

WHAT THIS MODULE DELIBERATELY DOES NOT DO
  It never guesses when there's nothing to resolve against (no current
  suspect, no last-turn results) — silence in that case is correct;
  the query just proceeds without a referent, same as before this
  module existed. It also never overrides an explicit name the officer
  already typed — pronoun resolution only fires when
  entities["person_name_candidates"] is empty.
"""
import re

_PRONOUN_PATTERN = re.compile(r'\b(he|him|his|she|her|they|them|their)\b', re.IGNORECASE)
_GANG_REF_PATTERN = re.compile(r'\b(that|this|the)\s+(gang|syndicate)\b', re.IGNORECASE)
_ORDINAL_MAP = {
    "first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2,
    "fourth": 3, "4th": 3, "fifth": 4, "5th": 4,
}
_ORDINAL_PATTERN = re.compile(
    r'\b(?:the\s+)?(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th)\s+'
    r'(one|result|person|case|record)\b', re.IGNORECASE
)


def resolve_references(message: str, entities: dict, working_context: dict, trace_log: list) -> dict:
    """
    Mutates and returns `entities` in place. Only ever ADDS information
    (a person name candidate, a resolved-gang hint) — never removes
    anything the officer actually typed.
    """
    has_explicit_name = bool(entities.get("person_name_candidates"))

    # ── Ordinal reference ("the second one") — resolved against exactly
    #    what was shown to the officer last turn, in the same order the
    #    panel displayed it. Checked before plain pronouns since "the
    #    second one" would otherwise never match the pronoun pattern
    #    anyway, but ordering keeps the intent explicit. ──────────────
    m = _ORDINAL_PATTERN.search(message)
    if m and not has_explicit_name:
        idx = _ORDINAL_MAP.get(m.group(1).lower())
        person_ids = working_context.get("last_turn_person_ids") or []
        fir_numbers = working_context.get("last_turn_fir_numbers") or []
        if idx is not None and idx < len(person_ids):
            entities["_reference_resolved_person_id"] = person_ids[idx]
            trace_log.append(
                f'Reference resolution: "{m.group(0)}" -> person_id={person_ids[idx]} '
                f"(item {idx + 1} of the previous turn's results)"
            )
        elif idx is not None and idx < len(fir_numbers):
            entities["fir_number_candidate"] = fir_numbers[idx]
            trace_log.append(
                f'Reference resolution: "{m.group(0)}" -> FIR {fir_numbers[idx]} '
                f"(item {idx + 1} of the previous turn's results)"
            )

    # ── Gang reference ("that gang", "the syndicate") ────────────────
    if _GANG_REF_PATTERN.search(message) and working_context.get("current_gang"):
        entities["_resolved_gang"] = working_context["current_gang"]
        trace_log.append(
            f'Reference resolution: "{_GANG_REF_PATTERN.search(message).group(0)}" -> '
            f'{working_context["current_gang"]} (gang last discussed in this session)'
        )

    # ── Pronoun ("he"/"she"/"they"/"his"/"her"/"their") -> current
    #    suspect in the officer's working context. Deliberately only
    #    fires when the officer didn't already type a name — an
    #    explicit name always wins. ─────────────────────────────────
    pm = _PRONOUN_PATTERN.search(message)
    current_suspect = working_context.get("current_suspect")
    if pm and not has_explicit_name and current_suspect and current_suspect.get("name"):
        resolved_name = current_suspect["name"]
        entities["person_name_candidates"] = [resolved_name]
        trace_log.append(
            f'Reference resolution: "{pm.group(0)}" -> {resolved_name} '
            f"(current suspect in this session's working context)"
        )

    return entities
