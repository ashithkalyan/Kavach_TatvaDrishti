"""
KAVACH Brain — Crime Forecasting Engine
===========================================
Transparent statistical time-series forecasting: trend decomposition +
seasonal indexing + event-based adjustment (a simplified, fully-shown-
working relative of Holt-Winters).

WHY NOT A "TRAINED ML MODEL"? On a dataset with a few dozen monthly
observations per district/crime-type pair, a complex trained model
would overfit and hand back a confident-looking number nobody could
actually justify. This approach shows its exact arithmetic — which is
what a resource-deployment decision needs before an SP reassigns night
patrols based on it. If KSP's real production data reaches the scale
where a trained model would have enough signal to be trustworthy, this
module's output format is the natural place to swap the internals
without touching anything downstream.

FEATURES USED (district x crime_type):
  - Historical monthly case counts -> trend slope + seasonal index
  - Festival-period flag       (Ganesh Chaturthi / Dasara / Diwali window)
  - Monsoon-period flag        (proxy for real IMD rainfall data)
  - Election-period flag       (proxy for real Election Commission calendar)

ON "COMMUNAL INCIDENT" FORECASTING: KAVACH deliberately does NOT score
areas or predict risk using religious or caste composition — that is
discriminatory profiling, not policing intelligence, regardless of
framing. What this module DOES forecast is event-driven public-order /
crowd-safety load: spikes tied to festival calendars and large-
gathering permits, which is standard emergency-management practice for
deployment planning — never targeting of any community.
"""
import math

FESTIVAL_MONTHS = {9, 10, 11}       # Ganesh Chaturthi / Dasara / Diwali window
MONSOON_MONTHS = {6, 7, 8, 9}       # synthetic rainfall proxy — swap for real IMD feed
PUBLIC_ORDER_CRIME_TYPES = {"Assault", "Dacoity", "Robbery"}  # crowd-safety-relevant categories


def _linear_trend(values: list) -> float:
    """Least-squares slope over an evenly spaced series — exact, explainable."""
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    x_mean, y_mean = sum(xs) / n, sum(values) / n
    num = sum((xs[i] - x_mean) * (values[i] - y_mean) for i in range(n))
    den = sum((x - x_mean) ** 2 for x in xs) or 1
    return num / den


def _seasonal_index(monthly_series: dict) -> dict:
    all_vals = [v for series in monthly_series.values() for v in series]
    overall_avg = (sum(all_vals) / len(all_vals)) if all_vals else 1.0
    return {
        m: (sum(v) / len(v)) / overall_avg if v and overall_avg else 1.0
        for m, v in monthly_series.items()
    }


def forecast_next_month(history: list, target_month: int, is_election_period: bool = False) -> dict:
    """
    history: [{"year":int,"month":int,"count":int}, ...] sorted chronologically,
             single district + crime_type series.
    """
    if len(history) < 6:
        return {
            "forecast": None, "confidence": "insufficient_data",
            "explanation": "Need at least 6 months of history for a reliable trend estimate.",
        }

    values = [h["count"] for h in history]
    trend_slope = _linear_trend(values)
    baseline = sum(values[-3:]) / min(3, len(values))

    monthly = {}
    for h in history:
        monthly.setdefault(h["month"], []).append(h["count"])
    seasonal_factor = _seasonal_index(monthly).get(target_month, 1.0)

    festival_factor = 1.18 if target_month in FESTIVAL_MONTHS else 1.0
    monsoon_factor = 1.08 if target_month in MONSOON_MONTHS else 1.0
    election_factor = 1.12 if is_election_period else 1.0

    forecast = baseline * seasonal_factor * festival_factor * monsoon_factor * election_factor
    forecast += trend_slope

    mean_v = sum(values) / len(values)
    variance = sum((v - mean_v) ** 2 for v in values) / len(values)
    std = math.sqrt(variance)
    cv = (std / mean_v) if mean_v else 1.0
    confidence = "high" if cv < 0.3 else ("medium" if cv < 0.6 else "low")
    direction = "increasing" if trend_slope > 0.5 else ("decreasing" if trend_slope < -0.5 else "stable")

    explanation_parts = [
        f"baseline {round(baseline, 1)}/month",
        f"seasonal factor {round(seasonal_factor, 2)}x",
        f"trend {direction} ({round(trend_slope, 2)}/month)",
    ]
    if festival_factor > 1:
        explanation_parts.append("festival-period uplift applied")
    if monsoon_factor > 1:
        explanation_parts.append("monsoon-period adjustment applied")
    if election_factor > 1:
        explanation_parts.append("election-period adjustment applied")

    return {
        "forecast": round(max(0, forecast), 1),
        "baseline_avg": round(baseline, 1),
        "trend_direction": direction,
        "trend_slope_per_month": round(trend_slope, 2),
        "seasonal_factor": round(seasonal_factor, 2),
        "festival_adjustment": festival_factor,
        "monsoon_adjustment": monsoon_factor,
        "election_adjustment": election_factor,
        "confidence": confidence,
        "explanation": ", ".join(explanation_parts),
    }


def flag_anomalies(history: list, threshold_std: float = 1.5) -> list:
    """Anomaly detection: months where actuals deviated sharply from the norm."""
    if len(history) < 6:
        return []
    values = [h["count"] for h in history]
    mean_v = sum(values) / len(values)
    std = math.sqrt(sum((v - mean_v) ** 2 for v in values) / len(values)) or 1
    flags = []
    for h in history:
        z = (h["count"] - mean_v) / std
        if abs(z) >= threshold_std:
            flags.append({
                **h, "z_score": round(z, 2),
                "note": "Sharp spike above historical norm" if z > 0 else "Sharp drop below historical norm",
            })
    return flags


def public_order_forecast(history: list, target_month: int) -> dict:
    """
    Event/calendar-driven crowd-safety load forecast — explicitly NOT
    a function of demographic or religious composition of the area.
    Only calendar signals (festival window) and historical public-order
    case volume are used.
    """
    base = forecast_next_month(history, target_month)
    if base.get("forecast") is None:
        return base
    return {
        **base,
        "deployment_note": (
            "Festival-window uplift applied — standard crowd-safety patrol "
            "planning, based only on the calendar and historical case volume "
            "for this category. No demographic or religious data is used in "
            "this forecast."
            if target_month in FESTIVAL_MONTHS else
            "No festival-window adjustment for this month."
        ),
    }
