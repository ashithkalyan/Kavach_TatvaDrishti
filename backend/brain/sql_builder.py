"""
KAVACH Brain — SQL Query Builder
====================================
Deterministic, template-based SQL generation against vw_fir_flat and
vw_person_flat (defined in seed_data.py's create_schema) — querying
flattened views instead of raw joins keeps every template here short
and auditable, and means the same templates keep working even if the
underlying normalised schema gains more tables later.

Every query is a parameterised SELECT — never string-interpolated
values — and every template is a plain, readable function, not a
generated string, so anyone on the team can read exactly what each
intent produces.

A few intents (prediction, similarity, timeline, recommendation,
network path-finding) aren't SQL at all — they route to their own
brain modules. build() signals this with {"route": "..."} instead of
{"sql": ...}, and brain.py (the orchestrator) dispatches accordingly.
"""

NON_SQL_INTENTS = {
    "prediction_query": "prediction_engine",
    "similarity_query": "similarity_engine",
    "timeline_query": "timeline_engine",
    "recommendation_query": "recommendation_engine",
}


def build(intent: str, entities: dict, resolved_names: list = None, limit: int = 30) -> dict:
    if intent in NON_SQL_INTENTS:
        return {"route": NON_SQL_INTENTS[intent], "sql": None}

    where, params = ["1=1"], []

    if entities.get("districts"):
        placeholders = ",".join("?" * len(entities["districts"]))
        where.append(f"district IN ({placeholders})")
        params += entities["districts"]

    if entities.get("crime_types"):
        placeholders = ",".join("?" * len(entities["crime_types"]))
        where.append(f"crime_type IN ({placeholders})")
        params += entities["crime_types"]

    if entities.get("date_from"):
        where.append("registration_date >= ?")
        params.append(entities["date_from"])

    # BUG FIX (see brain.py's process_query docstring / CHANGES4.md):
    # `resolved_names` is ALWAYS passed by brain.py's only caller (as
    # `alias_matches`, which is `[]` — not None — whenever name
    # candidates existed but none resolved to a real person). The old
    # `if resolved_names:` treated an EMPTY list the same as "resolution
    # was never attempted" and fell back to using the raw, unresolved
    # candidate text directly as a SQL name filter — meaning a word that
    # alias_resolver.py had already determined matches nobody (e.g.
    # "Urban", picked up as a stray capitalised word from "Bengaluru
    # Urban" and never resolved to any real person) still got used as a
    # `LIKE '%Urban%'` filter, silently turning an ordinary district
    # query into a person-scoped query that could only ever return zero
    # rows. Checking `is not None` instead means "resolution ran and
    # found nothing" correctly falls through to the ordinary
    # district/crime-type search below, while a genuine future caller
    # that skips resolution entirely (passing resolved_names=None) still
    # gets the raw-candidate fallback.
    name_terms = []
    if resolved_names is not None:
        name_terms = [m["name"] for m in resolved_names if m["confidence"] >= 0.7]
    elif entities.get("person_name_candidates"):
        name_terms = entities["person_name_candidates"]

    # For intents whose ENTIRE point IS a name search — person_lookup,
    # network_query (see brain.py's _NEEDS_NAME_INTENTS) — falling back
    # to the raw, unresolved candidate text as a literal search term is
    # correct and desired: the officer is deliberately searching by
    # name, so an honest "nobody by that name is on file" is the right
    # answer, not a silent substitution of an unconstrained "top N by
    # risk/centrality" list that has nothing to do with what was typed
    # (a real, reported bug — see person_lookup below). For every OTHER
    # intent (crime_type_search, statistics_query, etc.) a name is at
    # most an OPTIONAL extra filter, so a stray capitalised word that
    # never resolved to anyone (e.g. "Urban" out of "Bengaluru Urban")
    # is correctly dropped instead of hijacking the query — those
    # intents deliberately do NOT get this raw-text fallback.
    literal_name_terms = name_terms or (
        entities.get("person_name_candidates", []) if intent in ("person_lookup", "network_query") else []
    )

    # A person_id resolved directly by reference_resolver.py (e.g. "the
    # second one" -> last turn's 2nd result) — bypasses name matching
    # entirely since we already know exactly who is meant.
    resolved_person_id = entities.get("_reference_resolved_person_id")

    # ── intent-specific templates ────────────────────────────────────────
    if intent == "repeat_offender_search":
        threshold = entities.get("threshold")
        having = "prior_convictions >= 2"
        if threshold and threshold[0] in (">=", ">", "="):
            op = threshold[0]
            having = f"prior_convictions {op} ?"
            params_h = [threshold[1]]
        else:
            params_h = []
        sql = f"""
            SELECT person_id, name, alias, age, gender, district, risk_score, risk_category,
                   gang_affiliation, modus_operandi, prior_convictions
            FROM vw_person_flat WHERE is_repeat_offender=1 AND {having}
            ORDER BY prior_convictions DESC, risk_score DESC LIMIT {limit}
        """
        return {"sql": sql.strip(), "params": tuple(params_h), "target": "person",
                "intent_label": "Repeat offenders ranked by linked case count"}

    if intent == "risk_query":
        risk_filter = "risk_category IN ('EXTREME','HIGH')"
        sql = f"""
            SELECT person_id, name, alias, age, district, risk_score, risk_category,
                   gang_affiliation, prior_convictions
            FROM vw_person_flat WHERE {risk_filter}
            ORDER BY risk_score DESC LIMIT {limit}
        """
        return {"sql": sql.strip(), "params": (), "target": "person",
                "intent_label": "High and extreme risk identities"}

    if intent == "gang_query":
        gw, gp = ["gang_affiliation IS NOT NULL"], []
        resolved_gang = entities.get("_resolved_gang")
        if resolved_gang:
            gw.append("gang_affiliation = ?")
            gp.append(resolved_gang)
        sql = f"""
            SELECT person_id, name, alias, age, district, gang_affiliation, risk_score, risk_category,
                   prior_convictions
            FROM vw_person_flat WHERE {' AND '.join(gw)}
            ORDER BY risk_score DESC LIMIT {limit}
        """
        label = "Gang-affiliated identities"
        if resolved_gang:
            label = f'Gang-affiliated identities — "{resolved_gang}" (resolved from your reference)'
        return {"sql": sql.strip(), "params": tuple(gp), "target": "person", "intent_label": label}

    if intent == "person_lookup":
        if literal_name_terms:
            like_clauses = " OR ".join(["name LIKE ?"] * len(literal_name_terms))
            where.append(f"({like_clauses})")
            params += [f"%{n}%" for n in literal_name_terms]
        elif resolved_person_id:
            # "the second one" etc. — a direct in-session reference,
            # resolved by reference_resolver.py, with no typed name at all.
            where.append("person_id = ?")
            params.append(resolved_person_id)
        else:
            # No name was ever extracted at all. Shouldn't normally
            # happen — brain.py's clarification gate asks for a name
            # before this intent is ever routed here — but this is the
            # actual bug that was reported: falling through to an
            # unconstrained query here silently returned the top-30
            # highest-risk people in the ENTIRE state and let the reply
            # attribute that #1 person's profile to whatever the officer
            # actually typed (e.g. random gibberish). Force zero rows
            # instead of ever guessing who was meant.
            where.append("1=0")
        sql = f"""
            SELECT person_id, name, alias, age, gender, district, occupation, risk_score, risk_category,
                   gang_affiliation, modus_operandi, prior_convictions, is_repeat_offender
            FROM vw_person_flat WHERE {' AND '.join(where)}
            ORDER BY risk_score DESC LIMIT {limit}
        """
        return {"sql": sql.strip(), "params": tuple(params), "target": "person",
                "intent_label": f"Profile lookup" + (f' for "{", ".join(literal_name_terms)}"' if literal_name_terms else "")}

    if intent == "case_status_query":
        status_map = {"pending": "Under Investigation", "under investigation": "Under Investigation",
                       "charge sheet": "Charge-Sheeted", "chargesheet": "Charge-Sheeted", "closed": "Closed"}
        status = None
        text_l = " ".join(entities.get("_raw_text", "").lower().split()) if entities.get("_raw_text") else ""
        for k, v in status_map.items():
            if k in text_l:
                status = v
                break

        # Person-scoped path: "does HE have any pending cases?" needs to
        # filter by accused, but vw_fir_flat has no person column (a case
        # can have several accused) — so this joins through
        # PersonIdentity -> PersonIdentityLink -> Accused -> CaseMaster
        # instead of the flat view. Without this branch, a resolved
        # pronoun/name here was silently DROPPED and the query quietly
        # returned cases for every accused in the state, not the one
        # asked about.
        if name_terms or resolved_person_id:
            return _build_person_scoped_case_query(name_terms, resolved_person_id, status,
                                                     entities, limit, label="Case status search")

        if status:
            where.append("status=?")
            params.append(status)
        sql = f"""
            SELECT fir_number, registration_date, district, police_station, crime_type, status,
                   investigating_officer
            FROM vw_fir_flat WHERE {' AND '.join(where)}
            ORDER BY registration_date DESC LIMIT {limit}
        """
        return {"sql": sql.strip(), "params": tuple(params), "target": "fir",
                "intent_label": "Case status search"}

    if intent == "crime_type_search":
        # Same person-scoping need as case_status_query above — "what
        # has HE been accused of?" / "his theft cases" — only takes this
        # path when a name/reference actually resolved to someone;
        # otherwise falls through to the ordinary FIR search below.
        if name_terms or resolved_person_id:
            return _build_person_scoped_case_query(name_terms, resolved_person_id, None,
                                                     entities, limit, label="Person-scoped crime search")
        sql = f"""
            SELECT fir_number, registration_date, district, police_station, crime_type, status,
                   weapon_used, vehicle_involved, property_value
            FROM vw_fir_flat WHERE {' AND '.join(where)}
            ORDER BY registration_date DESC LIMIT {limit}
        """
        return {"sql": sql.strip(), "params": tuple(params), "target": "fir",
                "intent_label": "FIR search"}

    if intent in ("location_search", "statistics_query", "follow_up_filter", "general_search"):
        sql = f"""
            SELECT fir_number, registration_date, district, police_station, crime_type, status,
                   weapon_used, vehicle_involved, property_value
            FROM vw_fir_flat WHERE {' AND '.join(where)}
            ORDER BY registration_date DESC LIMIT {limit}
        """
        return {"sql": sql.strip(), "params": tuple(params), "target": "fir",
                "intent_label": "FIR search"}

    # network_query, gang path-finding etc. also route out — handled by graph_engine
    if intent == "network_query":
        return {"route": "graph_engine", "sql": None, "name_terms": literal_name_terms}

    # default fallback
    sql = f"""
        SELECT fir_number, registration_date, district, crime_type, police_station, status
        FROM vw_fir_flat ORDER BY registration_date DESC LIMIT {limit}
    """
    return {"sql": sql.strip(), "params": (), "target": "fir", "intent_label": "Recent FIRs"}


def _build_person_scoped_case_query(name_terms, resolved_person_id, status, entities, limit, label):
    """
    Cases tied to a SPECIFIC accused person — the join vw_fir_flat can't
    express, because one FIR can name several accused, so the flat view
    has no person column to filter on at all. Walks
    PersonIdentity -> PersonIdentityLink -> Accused -> CaseMaster instead.

    Reached from case_status_query / crime_type_search whenever a name or
    an in-session reference ("he", "the second one") resolved to someone —
    see reference_resolver.py and brain.py.
    """
    where, params = [], []

    if resolved_person_id:
        where.append("pi.PersonIdentityID = ?")
        params.append(resolved_person_id)
    elif name_terms:
        like_clauses = " OR ".join(["pi.CanonicalName LIKE ?"] * len(name_terms))
        where.append(f"({like_clauses})")
        params += [f"%{n}%" for n in name_terms]
    else:
        where.append("1=0")  # should never happen — caller only routes here with one of the above

    if status:
        where.append("csm.CaseStatusName = ?")
        params.append(status)
    if entities.get("districts"):
        placeholders = ",".join("?" * len(entities["districts"]))
        where.append(f"d.DistrictName IN ({placeholders})")
        params += entities["districts"]
    if entities.get("crime_types"):
        placeholders = ",".join("?" * len(entities["crime_types"]))
        where.append(f"csh.CrimeHeadName IN ({placeholders})")
        params += entities["crime_types"]
    if entities.get("date_from"):
        where.append("cm.CrimeRegisteredDate >= ?")
        params.append(entities["date_from"])

    sql = f"""
        SELECT DISTINCT
            cm.CrimeNo AS fir_number, cm.CrimeRegisteredDate AS registration_date,
            d.DistrictName AS district, u.UnitName AS police_station,
            csh.CrimeHeadName AS crime_type, csm.CaseStatusName AS status,
            cm.WeaponUsed AS weapon_used, cm.VehicleInvolved AS vehicle_involved,
            cfi.EstimatedLossValue AS property_value, pi.CanonicalName AS matched_person
        FROM PersonIdentity pi
        JOIN PersonIdentityLink pil ON pil.PersonIdentityID = pi.PersonIdentityID
        JOIN Accused a ON a.AccusedMasterID = pil.AccusedMasterID
        JOIN CaseMaster cm ON cm.CaseMasterID = a.CaseMasterID
        LEFT JOIN Unit u ON cm.PoliceStationID = u.UnitID
        LEFT JOIN District d ON u.DistrictID = d.DistrictID
        LEFT JOIN CrimeSubHead csh ON cm.CrimeMinorHeadID = csh.CrimeSubHeadID
        LEFT JOIN CaseStatusMaster csm ON cm.CaseStatusID = csm.CaseStatusID
        LEFT JOIN CaseFinancialImpact cfi ON cm.CaseMasterID = cfi.CaseMasterID
        WHERE {' AND '.join(where)}
        ORDER BY cm.CrimeRegisteredDate DESC LIMIT {limit}
    """
    return {"sql": sql.strip(), "params": tuple(params), "target": "fir", "intent_label": label}
