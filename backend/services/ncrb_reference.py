"""
KAVACH — Published NCRB Reference Data (real, sourced, small on purpose)
============================================================================
Every number below is a real, published, sourced statistic — from NCRB's
own "Crime in India" annual reports (via their official releases and
verified news coverage of those releases), not from this project's
seeded/synthetic FIR data. Each entry carries its source and year
explicitly so nothing here can be mistaken for a live API pull.

WHAT THIS IS FOR
  seed_data.py generates a synthetic 500-FIR demo dataset for local
  development and this hackathon build — real KSP data was never
  available to this project (see README.md's "Honest Limitations"
  section). This module gives officers/judges a real, published,
  Karnataka-specific reference point to compare that synthetic data's
  SHAPE against — proportions and directions of movement, not exact
  counts. It deliberately does NOT claim the two datasets should match
  numerically; they can't, because one is real and one is a random
  Faker-generated demo set built to a target size of 500 records.

WHAT THIS IS NOT
  Not a live NCRB API integration (no such public real-time API exists
  publicly for this data — NCRB publishes annual PDF/tabular reports,
  not a query endpoint) and not a claim that KAVACH's underlying
  architecture requires real data to work — it was BUILT to run on
  real KSP data; this table exists purely for honest, sourced context
  while that real data isn't yet plugged in.

Sources: NCRB "Crime in India" 2022 and 2023 annual reports, as
reported via Deccan Herald's coverage of the NCRB releases and NCRB's
own summary release. Figures current as of the most recent published
report (2023 data, released 2025) at the time this table was written.
"""

KARNATAKA_REFERENCE = [
    {
        "metric": "Murder cases registered (Karnataka, state-wide)",
        "year": 2023, "value": 1322,
        "note": "5.84% decrease from 2022 (1,404); 2021 figure was 1,357",
        "source": "NCRB Crime in India 2023",
    },
    {
        "metric": "Murder charge-sheeting rate (Karnataka, state-wide)",
        "year": 2023, "value_pct": 88.8,
        "note": None,
        "source": "NCRB Crime in India 2023",
    },
    {
        "metric": "Murders registered — Bengaluru city",
        "year": 2023, "value": 206,
        "note": "19.07% increase from 173 in 2022; city charge-sheeting rate 91%",
        "source": "NCRB Crime in India 2023",
    },
    {
        "metric": "Cyber-crime cases registered (Karnataka, state-wide)",
        "year": 2022, "value": 12556,
        "note": "2nd-highest of any state that year, after Telangana (15,297)",
        "source": "NCRB Crime in India 2022",
    },
    {
        "metric": "Crimes against senior citizens (Karnataka, state-wide)",
        "year": 2023, "value": 1840,
        "note": "649 of these in Bengaluru alone — a 41.7% rise in the city from 459 in 2022",
        "source": "NCRB Crime in India 2023",
    },
    {
        "metric": "IPC charge-sheet rate, national",
        "year": 2023, "value_pct": 72.7,
        "note": "conviction rate 54.0% — for context on typical charge-sheet-to-conviction gaps",
        "source": "NCRB Crime in India 2023",
    },
]


def get_reference_table():
    return KARNATAKA_REFERENCE


def compare_with_seeded_data(conn):
    """
    Pulls the comparable aggregate figures OUT OF THIS PROJECT'S OWN
    seeded database (not hardcoded) and pairs them with the published
    reference above, purely for side-by-side display — see the honesty
    note at the top of this file for why these are NOT expected to
    numerically match.
    """
    seeded_murder_count = conn.execute("""
        SELECT COUNT(*) FROM vw_fir_flat WHERE crime_type = 'Murder'
    """).fetchone()[0]
    seeded_total = conn.execute("SELECT COUNT(*) FROM vw_fir_flat").fetchone()[0]
    seeded_cyber_count = conn.execute("""
        SELECT COUNT(*) FROM vw_fir_flat WHERE crime_type = 'Cybercrime'
    """).fetchone()[0]

    return {
        "published_reference": KARNATAKA_REFERENCE,
        "this_projects_seeded_data": {
            "total_seeded_fir_records": seeded_total,
            "seeded_murder_count": seeded_murder_count,
            "seeded_murder_share_pct": round(100 * seeded_murder_count / seeded_total, 1) if seeded_total else None,
            "seeded_cybercrime_count": seeded_cyber_count,
            "seeded_cybercrime_share_pct": round(100 * seeded_cyber_count / seeded_total, 1) if seeded_total else None,
        },
        "disclaimer": (
            "The seeded dataset is synthetic demo data generated for development and this build — "
            "it is not expected to numerically match real published figures, and this comparison is "
            "not a claim that it does. It's shown so the proportions (e.g. what share of cases are a "
            "given crime type) can be sanity-checked against real, published Karnataka statistics "
            "instead of no external reference point at all."
        ),
    }
