"""
KAVACH Brain — Live Document Ingestion Engine
=================================================
Lets an investigator upload a new FIR as a PDF or a scanned photo and
have KAVACH extract structured fields for review, then commit the
confirmed record straight into the live database. Because every other
brain module (chat, similarity, network, prediction) reads directly
from that live database at query time — nothing is a frozen snapshot
or a fine-tuned model that needs retraining — a newly-ingested record
is queryable the instant it is confirmed. That is a genuine structural
advantage over "fine-tune an LLM on your data": no retraining step,
no reindexing delay, ever.

PIPELINE
  1. extract_text_from_pdf() / extract_text_from_image()
  2. parse_fields()      — best-effort structured draft, reusing the
                            same crime-type / district glossaries the
                            chat brain uses, so extraction and query
                            understanding stay in sync automatically
  3. (investigator reviews AND EDITS the draft in the UI — not this
      module's job; see Cases.jsx's UploadModal)
  4. commit_draft()      — writes the CONFIRMED fields to CaseMaster,
                            Accused, and Victim, and runs each new
                            accused through the SAME identity-resolution
                            and risk-scoring logic seed_data.py runs at
                            bulk-seed time (alias_resolver + services/
                            risk_scoring) — so a hand-typed correction
                            to an OCR guess gets exactly the same
                            cross-case linking a bulk import would.

HONESTY NOTE ON OCR: Tesseract (the OCR engine used here) is genuinely
reliable on clean typed/printed text. It is NOT reliable on handwritten
police forms — no OCR engine is, including commercial ones. Every
extraction returns a confidence score; low-confidence fields should be
routed to manual entry rather than silently trusted. KAVACH never
auto-commits an extracted guess — a human always confirms before
anything reaches the system of record.
"""
import re

from . import entity_extractor, alias_resolver, identity_confidence
from services import risk_scoring


def extract_text_from_pdf(filepath: str) -> dict:
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
        text = "\n".join(parts)
        return {"text": text, "engine": "pdfplumber", "success": bool(text.strip())}
    except Exception as e:
        return {"text": "", "engine": "pdfplumber", "success": False, "error": str(e)}


def extract_text_from_image(filepath: str) -> dict:
    """
    Returns extracted text AND a confidence score — the confidence is
    what lets the caller decide whether to trust the extraction or
    route straight to manual entry.
    """
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(filepath)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        words = [w for w in data["text"] if w.strip()]
        confs = [int(c) for c, w in zip(data["conf"], data["text"]) if w.strip() and str(c) != "-1"]
        text = " ".join(words)
        avg_conf = round(sum(confs) / len(confs), 1) if confs else 0.0
        return {
            "text": text, "engine": "tesseract", "avg_confidence": avg_conf,
            "success": bool(text.strip()),
            "reliability_note": (
                "High-confidence extraction — typed/printed text." if avg_conf >= 75 else
                "Low-confidence extraction — likely handwritten or poor scan quality. "
                "Route to manual entry rather than trusting this draft."
            ),
        }
    except Exception as e:
        return {"text": "", "engine": "tesseract", "avg_confidence": 0.0, "success": False, "error": str(e)}


_CRIME_NO_PATTERN = re.compile(r'\b\d{18}\b')
_DATE_PATTERNS = [
    re.compile(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b'),
    re.compile(r'\b(\d{4})-(\d{2})-(\d{2})\b'),
]
_AGE_PATTERN = re.compile(r'\bage[d]?\s*[:\-]?\s*(\d{1,3})\b', re.IGNORECASE)


def parse_fields(raw_text: str) -> dict:
    """Best-effort structured draft — every guess is explicitly flagged,
    nothing is silently assumed correct."""
    draft = {
        "crime_no_guess": None,
        "date_guess": None,
        "age_guess": None,
        "crime_types_detected": entity_extractor.extract_crime_types(raw_text),
        "districts_detected": entity_extractor.extract_districts(raw_text),
        "person_name_candidates": entity_extractor.extract_person_name_candidates(raw_text),
        "raw_text_preview": raw_text[:800],
        "extraction_notes": [],
    }

    m = _CRIME_NO_PATTERN.search(raw_text.replace(" ", ""))
    if m:
        draft["crime_no_guess"] = m.group(0)
    else:
        draft["extraction_notes"].append(
            "Could not confidently locate an 18-digit Crime Number — verify manually."
        )

    for pattern in _DATE_PATTERNS:
        m = pattern.search(raw_text)
        if m:
            draft["date_guess"] = m.group(0)
            break
    if not draft["date_guess"]:
        draft["extraction_notes"].append("No clearly formatted date found — enter manually.")

    m = _AGE_PATTERN.search(raw_text)
    if m:
        draft["age_guess"] = int(m.group(1))

    if not draft["crime_types_detected"]:
        draft["extraction_notes"].append("No recognised crime-type keyword found — select manually.")
    if not draft["districts_detected"]:
        draft["extraction_notes"].append("No recognised district found — select manually.")
    if not draft["person_name_candidates"]:
        draft["extraction_notes"].append("No candidate person names detected — verify manually.")

    draft["requires_manual_review"] = bool(draft["extraction_notes"])
    return draft


def ingest_document(filepath: str, file_kind: str) -> dict:
    """
    file_kind: 'pdf' | 'image'
    Top-level convenience wrapper: extract -> parse -> return draft for
    investigator review. Never touches the database — see commit_draft().
    """
    if file_kind == "pdf":
        extraction = extract_text_from_pdf(filepath)
    elif file_kind == "image":
        extraction = extract_text_from_image(filepath)
    else:
        return {"success": False, "error": f"Unsupported file_kind: {file_kind}"}

    if not extraction.get("success"):
        return {"success": False, "extraction": extraction, "draft": None}

    draft = parse_fields(extraction["text"])
    return {"success": True, "extraction": extraction, "draft": draft}


# ─── Live identity resolution (incremental equivalent of seed_data.py's
#     bulk alias_resolver.cluster_identities() pass) ───────────────────

def resolve_or_link_person_identity(conn, name: str, age, district_id, age_tolerance: int = 2) -> dict:
    """
    For ONE newly-ingested accused, decides whether they are (probably)
    an existing PersonIdentity or a brand-new one — same rule
    cluster_identities() uses at bulk-seed time (same district + age
    within tolerance + resolve_name confidence >= 0.78), just applied
    incrementally against identities that already exist in the live DB
    instead of batch-clustering a whole raw list at once.
    """
    if age is None or district_id is None:
        return {"person_identity_id": None, "is_new": True, "match_confidence": 1.0,
                "match_method": "single_record", "matched_against": None}

    candidates = conn.execute(
        "SELECT PersonIdentityID, CanonicalName, AgeYear FROM PersonIdentity WHERE DistrictID=?",
        (district_id,),
    ).fetchall()

    best = None
    for pid, canon_name, cand_age in candidates:
        if cand_age is None or abs(cand_age - age) > age_tolerance:
            continue
        matches = alias_resolver.resolve_name(name, [canon_name])
        if matches and matches[0]["confidence"] >= 0.78:
            if best is None or matches[0]["confidence"] > best["match_confidence"]:
                best = {"person_identity_id": pid, "match_confidence": matches[0]["confidence"],
                        "match_method": matches[0]["method"], "matched_against": canon_name, "is_new": False}

    if best:
        return best
    return {"person_identity_id": None, "is_new": True, "match_confidence": 1.0,
            "match_method": "single_record", "matched_against": None}


def _crime_types_for_identity(conn, person_identity_id: int) -> list:
    rows = conn.execute("""
        SELECT DISTINCT csh.CrimeHeadName FROM PersonIdentityLink pil
        JOIN Accused a ON pil.AccusedMasterID = a.AccusedMasterID
        JOIN CaseMaster cm ON a.CaseMasterID = cm.CaseMasterID
        LEFT JOIN CrimeSubHead csh ON cm.CrimeMinorHeadID = csh.CrimeSubHeadID
        WHERE pil.PersonIdentityID = ?
    """, (person_identity_id,)).fetchall()
    return [r[0] for r in rows if r[0]]


def commit_draft(conn, confirmed_fields: dict, confirmed_by_employee_id: int) -> dict:
    """
    Writes an investigator-CONFIRMED draft into CaseMaster, Accused, and
    Victim. Only ever called after a human has reviewed and corrected
    the extracted draft — KAVACH never auto-commits an OCR/PDF guess
    straight into the system of record.

    confirmed_fields expected keys:
      crime_no, case_no, registration_date, police_station_id  (required)
      case_category_id, crime_major_head_id, crime_minor_head_id,
      case_status_id, brief_facts                              (optional)
      accused: [{name, age, gender, father_or_spouse_name}, ...]
      victims: [{name, age, gender}, ...]
      act_sections: [{act_code, section_code}, ...]

    Every new accused is run through resolve_or_link_person_identity()
    and services/risk_scoring.compute_risk_score() so a live-ingested
    record gets exactly the same cross-case identity linking and risk
    scoring a bulk-seeded one would — it is queryable, risk-scored, and
    network-linkable the instant this function returns.
    """
    required = ["crime_no", "case_no", "registration_date", "police_station_id"]
    missing = [f for f in required if not confirmed_fields.get(f)]
    if missing:
        return {"success": False, "error": f"Missing required fields: {missing}"}

    existing = conn.execute("SELECT CaseMasterID FROM CaseMaster WHERE CrimeNo=?",
                             (confirmed_fields["crime_no"],)).fetchone()
    if existing:
        return {"success": False, "error": f"A case with Crime Number {confirmed_fields['crime_no']} already "
                                            f"exists (CaseMasterID {existing[0]}) — this looks like a duplicate upload."}

    station_row = conn.execute("SELECT DistrictID FROM Unit WHERE UnitID=?",
                                (confirmed_fields["police_station_id"],)).fetchone()
    district_id = station_row[0] if station_row else None

    cur = conn.execute(
        """INSERT INTO CaseMaster
           (CrimeNo, CaseNo, CrimeRegisteredDate, PolicePersonID, PoliceStationID,
            CaseCategoryID, CrimeMajorHeadID, CrimeMinorHeadID, CaseStatusID, BriefFacts)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            confirmed_fields["crime_no"], confirmed_fields["case_no"],
            confirmed_fields["registration_date"], confirmed_by_employee_id,
            confirmed_fields["police_station_id"],
            confirmed_fields.get("case_category_id", 1),
            confirmed_fields.get("crime_major_head_id"),
            confirmed_fields.get("crime_minor_head_id"),
            confirmed_fields.get("case_status_id", 1),
            confirmed_fields.get("brief_facts", ""),
        ),
    )
    case_master_id = cur.lastrowid

    this_crime_type = None
    if confirmed_fields.get("crime_minor_head_id"):
        row = conn.execute("SELECT CrimeHeadName FROM CrimeSubHead WHERE CrimeSubHeadID=?",
                            (confirmed_fields["crime_minor_head_id"],)).fetchone()
        this_crime_type = row[0] if row else None

    accused_results = []
    for person in confirmed_fields.get("accused", []) or []:
        if not person.get("name"):
            continue
        person_no = f"A{len(accused_results) + 1}"
        acur = conn.execute(
            """INSERT INTO Accused (CaseMasterID, AccusedName, AgeYear, GenderID, PersonID, FatherOrSpouseName)
               VALUES (?,?,?,?,?,?)""",
            (case_master_id, person["name"], person.get("age"), person.get("gender"),
             person_no, person.get("father_or_spouse_name")),
        )
        accused_master_id = acur.lastrowid

        match = resolve_or_link_person_identity(conn, person["name"], person.get("age"), district_id)

        if match["is_new"]:
            crimes_committed = [this_crime_type] if this_crime_type else []
            risk = risk_scoring.compute_risk_score(
                prior_convictions=0, crimes_committed=crimes_committed,
                network_size=0, active_cases=1, years_active=1, gang_affiliated=False,
            )
            picur = conn.execute(
                """INSERT INTO PersonIdentity
                   (CanonicalName, AgeYear, GenderID, DistrictID, RiskScore, RiskCategory,
                    IsRepeatOffender, FatherOrSpouseName)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (person["name"], person.get("age"), person.get("gender"), district_id,
                 risk["score"], risk["category"], 0, person.get("father_or_spouse_name")),
            )
            person_identity_id = picur.lastrowid
            conn.execute(
                "INSERT INTO PersonIdentityLink (PersonIdentityID, AccusedMasterID, MatchConfidence, MatchMethod) "
                "VALUES (?,?,?,?)",
                (person_identity_id, accused_master_id, 1.0, "single_record"),
            )
        else:
            person_identity_id = match["person_identity_id"]
            prior_links = conn.execute(
                "SELECT COUNT(*) FROM PersonIdentityLink WHERE PersonIdentityID=?", (person_identity_id,)
            ).fetchone()[0]
            network_size = conn.execute(
                "SELECT COUNT(*) FROM PersonNetworkLink WHERE PersonIdentityID_A=? OR PersonIdentityID_B=?",
                (person_identity_id, person_identity_id),
            ).fetchone()[0]
            crimes_committed = _crime_types_for_identity(conn, person_identity_id)
            if this_crime_type:
                crimes_committed.append(this_crime_type)
            gang_row = conn.execute("SELECT GangAffiliation FROM PersonIdentity WHERE PersonIdentityID=?",
                                     (person_identity_id,)).fetchone()
            risk = risk_scoring.compute_risk_score(
                prior_convictions=prior_links, crimes_committed=crimes_committed,
                network_size=network_size, active_cases=1, years_active=1,
                gang_affiliated=bool(gang_row and gang_row[0]),
            )
            conn.execute(
                "UPDATE PersonIdentity SET RiskScore=?, RiskCategory=?, IsRepeatOffender=1 WHERE PersonIdentityID=?",
                (risk["score"], risk["category"], person_identity_id),
            )
            conn.execute(
                "INSERT INTO PersonIdentityLink (PersonIdentityID, AccusedMasterID, MatchConfidence, MatchMethod) "
                "VALUES (?,?,?,?)",
                (person_identity_id, accused_master_id, match["match_confidence"], match["match_method"]),
            )

        accused_results.append({
            "accused_master_id": accused_master_id, "name": person["name"],
            "person_identity_id": person_identity_id, "linked_to_existing_identity": not match["is_new"],
            "matched_against": match.get("matched_against"), "match_confidence": match["match_confidence"],
            "risk_score": risk["score"], "risk_category": risk["category"],
            # New evidence just arrived for this identity (a new linked
            # case record, either creating it or corroborating/
            # contradicting an existing one) — recompute and, if it
            # meaningfully changed, log a new point in its confidence
            # trajectory. See identity_confidence.py's module docstring
            # for why this is recomputed from scratch every time rather
            # than incrementally patched.
            "identity_confidence": identity_confidence.record_confidence_snapshot(conn, person_identity_id),
        })

    victim_count = 0
    for victim in confirmed_fields.get("victims", []) or []:
        if not victim.get("name"):
            continue
        conn.execute(
            "INSERT INTO Victim (CaseMasterID, VictimName, AgeYear, GenderID) VALUES (?,?,?,?)",
            (case_master_id, victim["name"], victim.get("age"), victim.get("gender")),
        )
        victim_count += 1

    for act_section in confirmed_fields.get("act_sections", []) or []:
        if act_section.get("act_code"):
            conn.execute(
                "INSERT INTO ActSectionAssociation (CaseMasterID, ActID, SectionID) VALUES (?,?,?)",
                (case_master_id, act_section.get("act_code"), act_section.get("section_code")),
            )

    conn.commit()
    fir_row = conn.execute("SELECT CrimeNo FROM CaseMaster WHERE CaseMasterID=?", (case_master_id,)).fetchone()

    return {
        "success": True, "case_master_id": case_master_id, "fir_number": fir_row[0] if fir_row else None,
        "accused": accused_results, "victims_added": victim_count,
        "note": "Record is now live — immediately queryable by chat, similarity, and network engines. "
                "No retraining or reindexing needed.",
    }
