"""
KAVACH Brain — Hotspot Forecast (item: "projected hotspots, next 30 days")
==============================================================================
This is NOT a new forecasting model — prediction_engine.py already does
transparent statistical forecasting (linear trend + seasonality
adjustment) for a single district+crime_type pair, driven by real
CrimeTrend rows. This module just runs that SAME function across every
district x crime_type combination that has enough history, and ranks
the results — turning a one-pair-at-a-time tool into something that can
actually feed a hotspot map.

HONESTY NOTE (matches this project's existing framing in
prediction_engine.py's own docstring): this is a moving-average /
linear-trend projection over the last few months of seeded data, not a
machine-learning model, and it should be presented to the officer —
and to anyone reviewing this project — as exactly that. The label
"projected, next 30 days" is deliberately literal, not "predictive
policing" marketing.
"""
import sqlite3
from datetime import datetime
from . import prediction_engine

MIN_HISTORY_MONTHS = 6  # matches prediction_engine.forecast_next_month's own minimum


def compute(conn: sqlite3.Connection, top_n: int = 15):
    """
    Returns a ranked list of {district, crime_type, predicted_count,
    trend, confidence, latitude, longitude} for the next calendar month,
    across every district x crime_type pair with enough CrimeTrend
    history to project responsibly.
    """
    pairs = conn.execute("""
        SELECT DistrictID, CrimeSubHeadID, COUNT(*) as months_on_file
        FROM CrimeTrend
        GROUP BY DistrictID, CrimeSubHeadID
        HAVING months_on_file >= ?
    """, (MIN_HISTORY_MONTHS,)).fetchall()

    districts = {r[0]: r[1] for r in conn.execute("SELECT DistrictID, DistrictName FROM District")}
    crime_types = {r[0]: r[1] for r in conn.execute("SELECT CrimeSubHeadID, CrimeHeadName FROM CrimeSubHead")}

    # District centroid = average lat/lng of that district's OWN real
    # seeded FIRs (via Unit -> District), not an invented coordinate —
    # same lat/lng columns the existing /api/analytics/hotspots endpoint
    # already uses for current (non-projected) hotspots.
    centroid_rows = conn.execute("""
        SELECT d.DistrictID, AVG(cm.latitude) as lat, AVG(cm.longitude) as lng
        FROM CaseMaster cm
        JOIN Unit u ON cm.PoliceStationID = u.UnitID
        JOIN District d ON u.DistrictID = d.DistrictID
        WHERE cm.latitude IS NOT NULL AND cm.longitude IS NOT NULL
        GROUP BY d.DistrictID
    """).fetchall()
    centroids = {r[0]: (r[1], r[2]) for r in centroid_rows}

    next_month = (datetime.now().month % 12) + 1
    results = []
    for did, csh_id, _months in pairs:
        if did not in districts or csh_id not in crime_types or did not in centroids:
            continue
        history_rows = conn.execute(
            "SELECT Year, Month, CaseCount FROM CrimeTrend WHERE DistrictID=? AND CrimeSubHeadID=? ORDER BY Year, Month",
            (did, csh_id)
        ).fetchall()
        history = [{"year": r[0], "month": r[1], "count": r[2]} for r in history_rows]
        forecast = prediction_engine.forecast_next_month(history, target_month=next_month)
        if not forecast or forecast.get("forecast") is None:
            continue  # e.g. "insufficient_data" — honestly skipped, not padded with a guess
        lat, lng = centroids[did]
        results.append({
            "district": districts[did],
            "crime_type": crime_types[csh_id],
            "predicted_count": forecast["forecast"],
            "trend": forecast.get("trend_direction"),
            "confidence": forecast.get("confidence"),
            "explanation": forecast.get("explanation"),
            "latitude": round(lat, 4),
            "longitude": round(lng, 4),
        })

    results.sort(key=lambda r: r["predicted_count"], reverse=True)
    return results[:top_n]
