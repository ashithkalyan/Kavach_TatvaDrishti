"""
KAVACH Brain — Police Terminology & Abbreviation Glossary
=============================================================
A plain, extensible lookup table. Used two ways:
  1. QUERY EXPANSION — "show me BNS 103 cases" gets recognised as a
     murder-adjacent query even though "BNS 103" alone means nothing
     to the crime-type keyword matcher.
  2. RESPONSE CLARITY — when KAVACH's answer contains a term a
     policymaker or junior analyst might not know, it can expand it on
     first use, since the challenge brief explicitly names
     "policymakers" as a target user alongside investigators.

A couple of entries are marked (verify) — these are abbreviations
where usage can vary by state/department; confirm exact KSP usage
with a domain mentor before presenting as authoritative.
"""
import re

POLICE_ABBREVIATIONS = {
    "FIR":   "First Information Report",
    "UDR":   "Unnatural Death Report",
    "PAR":   "Preliminary Arrest Report (verify exact KSP usage)",
    "IPC":   "Indian Penal Code",
    "CrPC":  "Code of Criminal Procedure",
    "BNS":   "Bharatiya Nyaya Sanhita — replaced the IPC nationwide, effective July 2024",
    "BNSS":  "Bharatiya Nagarik Suraksha Sanhita — replaced the CrPC, effective July 2024",
    "BSA":   "Bharatiya Sakshya Adhiniyam — replaced the Indian Evidence Act, effective July 2024",
    "NDPS":  "Narcotic Drugs and Psychotropic Substances Act",
    "POCSO": "Protection of Children from Sexual Offences Act",
    "MV Act":"Motor Vehicles Act",
    "IT Act":"Information Technology Act",
    "FSL":   "Forensic Science Laboratory",
    "CDR":   "Call Detail Record",
    "AFIS":  "Automated Fingerprint Identification System",
    "MO":    "Modus Operandi",
    "IO":    "Investigating Officer",
    "SHO":   "Station House Officer",
    "PC":    "Police Constable",
    "HC":    "Head Constable",
    "ASI":   "Assistant Sub-Inspector",
    "PSI":   "Police Sub-Inspector",
    "PI":    "Police Inspector",
    "CPI":   "Circle Police Inspector",
    "ACP":   "Assistant Commissioner of Police",
    "DCP":   "Deputy Commissioner of Police",
    "SP":    "Superintendent of Police",
    "DySP":  "Deputy Superintendent of Police",
    "DIG":   "Deputy Inspector General of Police",
    "IG":    "Inspector General of Police",
    "ADGP":  "Additional Director General of Police",
    "DGP":   "Director General of Police",
    "SCRB":  "State Crime Records Bureau",
    "NCRB":  "National Crime Records Bureau",
    "CCTNS": "Crime and Criminal Tracking Network & Systems",
}

# Reverse index for fast lookup during query expansion (case-insensitive,
# strips periods so "Dy.S.P." and "DySP" both resolve)
_NORMALISED_INDEX = {
    re.sub(r'[.\s]', '', k).lower(): (k, v)
    for k, v in POLICE_ABBREVIATIONS.items()
}


def expand(term: str):
    """Returns (canonical_abbreviation, full_form) or None."""
    key = re.sub(r'[.\s]', '', term).lower()
    return _NORMALISED_INDEX.get(key)


def expand_all_in_text(text: str) -> list:
    """Scan free text for any known abbreviation and return the hits found —
    used to enrich a response with expansions on first mention."""
    hits = []
    for token in re.findall(r"[A-Za-z]{2,6}", text):
        found = expand(token)
        if found and found not in hits:
            hits.append(found)
    return hits
