"""
KAVACH Brain — Prediction Accuracy Tracking
===============================================
Closes the loop prediction_engine.py's own docstring describes but
never acted on: every forecast KAVACH makes is stored here, and once
the target month's real case data exists, this module compares the
stored forecast against what actually happened and records the result
PERMANENTLY — turning "trust our forecast" into "here is our
historical track record."

Nothing here is a new forecasting method — prediction_engine.py is
still the only place a forecast number is ever computed. This module
only stores what was predicted, and later, what turned out to be true.

THE CORE HONESTY RULE, enforced in code, not just described: a forecast
is recorded EXACTLY ONCE per (district, crime type, target year, target
month) — see record_prediction()'s idempotency — and is trained ONLY on
data strictly before the target month (both here and in
backfill_historical_predictions()). A forecast that peeked at its own
target month's data, or that could be quietly re-recorded after seeing
more recent trends, would make the entire accuracy record meaningless.
Once settled, a prediction's outcome is never touched again either.

backfill_historical_predictions() is what makes this demonstrable
immediately rather than waiting years for real predictions to age into
a track record: it walks forward through this project's own seeded
CrimeTrend history and retroactively records what
forecast_next_month() WOULD have forecast at each point in time, using
strictly prior data only (real walk-forward backtesting — a standard,
legitimate evaluation methodology, not a shortcut), then settles each
one immediately since the "actual" outcome is already on file. This is
what turns the very first datathon demo into "here is our accuracy
across N settled forecasts" instead of an empty table.
"""
import sqlite3


def init_schema(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prediction_log (
            prediction_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            district_id       INTEGER NOT NULL,
            crime_subhead_id  INTEGER NOT NULL,
            target_year       INTEGER NOT NULL,
            target_month      INTEGER NOT NULL,
            predicted_count   REAL NOT NULL,
            baseline_avg      REAL,
            trend_direction   TEXT,
            confidence        TEXT,
            explanation       TEXT,
            made_by           INTEGER,
            made_at           TEXT DEFAULT CURRENT_TIMESTAMP,
            actual_count      REAL,             -- NULL until settled
            settled_at        TEXT,
            percent_error     REAL,             -- NULL until settled
            direction_correct INTEGER,          -- NULL until settled; 0/1
            UNIQUE(district_id, crime_subhead_id, target_year, target_month)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_prediction_log_target
        ON prediction_log (target_year, target_month)
    """)
    conn.commit()


def record_prediction(conn: sqlite3.Connection, district_id: int, crime_subhead_id: int,
                       target_year: int, target_month: int, forecast: dict, made_by: int = None) -> dict:
    """
    Stores a forecast for later accuracy comparison. Idempotent per
    (district, crime type, target year, target month): if this exact
    target was already predicted before (by anyone), the ORIGINAL
    stored prediction is left untouched and its id returned — a
    forecast does not get to be quietly revised after the fact just
    because someone asked again with more recent trend data available,
    which would defeat the entire point of tracking accuracy.

    Returns {"stored": bool, "prediction_id": int|None, "reason": str|None}.
    """
    existing = conn.execute(
        """SELECT prediction_id FROM prediction_log
           WHERE district_id=? AND crime_subhead_id=? AND target_year=? AND target_month=?""",
        (district_id, crime_subhead_id, target_year, target_month),
    ).fetchone()
    if existing:
        return {"stored": False, "prediction_id": existing[0], "reason": "already recorded for this target"}

    if forecast is None or forecast.get("forecast") is None:
        return {"stored": False, "prediction_id": None, "reason": "insufficient_data — not recorded"}

    cur = conn.execute(
        """INSERT INTO prediction_log
               (district_id, crime_subhead_id, target_year, target_month, predicted_count,
                baseline_avg, trend_direction, confidence, explanation, made_by)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (district_id, crime_subhead_id, target_year, target_month, forecast["forecast"],
         forecast.get("baseline_avg"), forecast.get("trend_direction"), forecast.get("confidence"),
         forecast.get("explanation"), made_by),
    )
    conn.commit()
    return {"stored": True, "prediction_id": cur.lastrowid, "reason": None}


def settle_due_predictions(conn: sqlite3.Connection) -> int:
    """
    Finds every unsettled prediction whose target month now has real
    CrimeTrend data on file, and settles it: records the actual count,
    the percent error, and whether the predicted DIRECTION
    (increasing/decreasing/stable, vs the month immediately before the
    target) matched what actually happened. Safe to call as often as
    you like — already-settled predictions are never re-touched (an
    outcome, once recorded, is as permanent as the forecast itself —
    see record_prediction()'s docstring for the same principle applied
    to the other end of this loop).

    Returns how many predictions were newly settled this call.
    """
    unsettled = conn.execute(
        """SELECT prediction_id, district_id, crime_subhead_id, target_year, target_month,
                  predicted_count, trend_direction
           FROM prediction_log WHERE actual_count IS NULL"""
    ).fetchall()

    settled_count = 0
    for pid, did, csh, ty, tm, predicted, trend_dir in unsettled:
        actual_row = conn.execute(
            "SELECT CaseCount FROM CrimeTrend WHERE DistrictID=? AND CrimeSubHeadID=? AND Year=? AND Month=?",
            (did, csh, ty, tm),
        ).fetchone()
        if not actual_row:
            continue  # target month hasn't happened / isn't on file yet — stays unsettled
        actual = actual_row[0]

        if actual:
            pct_error = round(abs(predicted - actual) / actual * 100, 1)
        else:
            pct_error = 0.0 if predicted == 0 else 100.0

        # Direction check: what ACTUALLY happened vs the month right
        # before the target, then compare that to what was predicted.
        # A +/-5% band around the previous month counts as "stable" on
        # both sides, matching forecast_next_month()'s own thresholding
        # style (it uses a small slope band the same way).
        prev_month, prev_year = (tm - 1, ty) if tm > 1 else (12, ty - 1)
        prev_row = conn.execute(
            "SELECT CaseCount FROM CrimeTrend WHERE DistrictID=? AND CrimeSubHeadID=? AND Year=? AND Month=?",
            (did, csh, prev_year, prev_month),
        ).fetchone()
        direction_correct = None
        if prev_row is not None and trend_dir in ("increasing", "decreasing", "stable"):
            prev_val = prev_row[0]
            if prev_val:
                actual_direction = ("increasing" if actual > prev_val * 1.05 else
                                     "decreasing" if actual < prev_val * 0.95 else "stable")
                direction_correct = int(actual_direction == trend_dir)

        conn.execute(
            """UPDATE prediction_log SET actual_count=?, settled_at=CURRENT_TIMESTAMP,
               percent_error=?, direction_correct=? WHERE prediction_id=?""",
            (actual, pct_error, direction_correct, pid),
        )
        settled_count += 1

    if settled_count:
        conn.commit()
    return settled_count


def accuracy_summary(conn: sqlite3.Connection, district_id: int = None, crime_subhead_id: int = None) -> dict:
    """
    The historical accuracy record for SETTLED predictions only —
    optionally scoped to one district and/or crime type. Computed the
    same way every time from the permanent settled log, never a
    marketing figure. {"settled_count": 0, ...None fields} when nothing
    has settled yet, which is an honest, expected state for a brand new
    district/crime-type pair, not an error.
    """
    where, params = ["actual_count IS NOT NULL"], []
    if district_id:
        where.append("district_id=?"); params.append(district_id)
    if crime_subhead_id:
        where.append("crime_subhead_id=?"); params.append(crime_subhead_id)
    where_sql = " AND ".join(where)

    rows = conn.execute(
        f"SELECT percent_error, direction_correct FROM prediction_log WHERE {where_sql}", params
    ).fetchall()

    if not rows:
        return {"settled_count": 0, "mean_percent_error": None, "median_percent_error": None,
                "within_20_percent_pct": None, "direction_accuracy_pct": None}

    errors = sorted(r[0] for r in rows if r[0] is not None)
    directions = [r[1] for r in rows if r[1] is not None]

    return {
        "settled_count": len(rows),
        "mean_percent_error": round(sum(errors) / len(errors), 1) if errors else None,
        "median_percent_error": round(errors[len(errors) // 2], 1) if errors else None,
        "within_20_percent_pct": round(100 * sum(1 for e in errors if e <= 20) / len(errors), 1) if errors else None,
        "direction_accuracy_pct": round(100 * sum(directions) / len(directions), 1) if directions else None,
    }


def list_predictions(conn: sqlite3.Connection, district_id: int = None, crime_subhead_id: int = None,
                      limit: int = 50) -> list:
    """Recent predictions (settled and unsettled) with human-readable
    district/crime-type names, newest target first — feeds a results
    table in the UI."""
    where, params = ["1=1"], []
    if district_id:
        where.append("p.district_id=?"); params.append(district_id)
    if crime_subhead_id:
        where.append("p.crime_subhead_id=?"); params.append(crime_subhead_id)
    where_sql = " AND ".join(where)

    rows = conn.execute(f"""
        SELECT p.prediction_id, d.DistrictName, cs.CrimeHeadName, p.target_year, p.target_month,
               p.predicted_count, p.actual_count, p.percent_error, p.direction_correct,
               p.confidence, p.made_at, p.settled_at
        FROM prediction_log p
        JOIN District d ON p.district_id = d.DistrictID
        JOIN CrimeSubHead cs ON p.crime_subhead_id = cs.CrimeSubHeadID
        WHERE {where_sql}
        ORDER BY p.target_year DESC, p.target_month DESC, p.prediction_id DESC LIMIT ?
    """, params + [limit]).fetchall()

    return [
        {"prediction_id": r[0], "district": r[1], "crime_type": r[2], "target_year": r[3], "target_month": r[4],
         "predicted_count": r[5], "actual_count": r[6], "percent_error": r[7],
         "direction_correct": (bool(r[8]) if r[8] is not None else None),
         "confidence": r[9], "made_at": r[10], "settled_at": r[11]}
        for r in rows
    ]


def backfill_historical_predictions(conn: sqlite3.Connection, made_by: int = None, min_history_months: int = 6) -> int:
    """
    One-time, idempotent walk-forward backtest across this project's
    ENTIRE seeded CrimeTrend history — see this module's docstring for
    why this is legitimate methodology (never a peek at the target
    month) and why it matters for a first demo. Safe to re-run: already-
    recorded targets are skipped via record_prediction()'s own
    idempotency, so calling this again after new CrimeTrend months
    arrive only fills in the new ones.

    Returns how many NEW predictions were stored.
    """
    from . import prediction_engine

    pairs = conn.execute(f"""
        SELECT DistrictID, CrimeSubHeadID FROM CrimeTrend
        GROUP BY DistrictID, CrimeSubHeadID HAVING COUNT(*) >= ?
    """, (min_history_months + 3,)).fetchall()

    stored = 0
    for did, csh in pairs:
        history_rows = conn.execute(
            "SELECT Year, Month, CaseCount FROM CrimeTrend WHERE DistrictID=? AND CrimeSubHeadID=? ORDER BY Year, Month",
            (did, csh),
        ).fetchall()
        full_history = [{"year": r[0], "month": r[1], "count": r[2]} for r in history_rows]

        for i in range(min_history_months, len(full_history)):
            target = full_history[i]
            prior = full_history[:i]  # strictly before the target — never a peek
            forecast = prediction_engine.forecast_next_month(prior, target_month=target["month"])
            if forecast.get("forecast") is None:
                continue
            result = record_prediction(conn, did, csh, target["year"], target["month"], forecast, made_by=made_by)
            if result["stored"]:
                stored += 1

    return stored
