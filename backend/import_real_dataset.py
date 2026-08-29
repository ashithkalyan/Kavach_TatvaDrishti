"""
KAVACH — Real KSP Dataset Importer (TEMPLATE — needs your file's actual columns)
====================================================================================
IMPORTANT, READ THIS FIRST:
No row-level KSP datathon dataset (actual FIR/accused/victim records) was
available when this script was written — only the project's own code
(whose seed_data.py generates 500 FAKER-based synthetic FIRs) and the
Police_FIR_ER_Diagram PDF, which is schema documentation (table/column
definitions) and contains no actual data rows. This script is therefore
a READY-TO-ADAPT SCAFFOLD, not a working one-command fix — you need to
point COLUMN_MAPPING below at your real file's actual column names
before running it. Do not run this expecting it to "just work" against
an unseen file format; it is deliberately built to fail loudly (a clear
KeyError on a missing column) rather than silently importing garbage.

WHAT THIS DOES
  1. Wipes the database and rebuilds the schema + Karnataka reference
     data (districts, police stations, crime taxonomy, the 4 demo
     logins) by reusing seed_data.py's create_schema()/seed_reference_data()
     — that reference data is real Karnataka government structure, not
     synthetic content, so it's kept regardless of where your FIR rows
     come from.
  2. Reads your dataset (CSV by default; see --format below) and, for
     each row, builds the SAME confirmed_fields payload the live
     document-ingestion UI produces, then calls
     brain/ingestion_engine.py's commit_draft() — meaning your bulk
     import gets EXACTLY the same accused identity-resolution and risk
     scoring as a one-at-a-time officer upload would.

WHAT YOU NEED TO DO
  1. Put your real dataset file somewhere accessible.
  2. Edit COLUMN_MAPPING below to match your file's actual column
     headers (open the file and check — don't guess).
  3. If your file has multiple accused/victims per row (e.g. semicolon-
     separated names in one cell), adjust _split_multi() below to match
     your file's actual convention.
  4. Run:  python import_real_dataset.py --file /path/to/your/data.csv --confirm-wipe

USAGE
  python import_real_dataset.py --file data.csv --confirm-wipe
  python import_real_dataset.py --file data.csv --confirm-wipe --dry-run   # validate without writing
"""
import argparse
import csv
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seed_data import create_schema, seed_reference_data, DB_PATH  # noqa: E402
from brain import ingestion_engine  # noqa: E402

# ─── EDIT THIS to match your real file's column headers ────────────────
# Left side = what this script looks for. Right side = your file's
# actual header name. Open your CSV/export in a text editor or Excel
# and copy the exact header text — including capitalisation.
COLUMN_MAPPING = {
    "crime_no": "CrimeNo",
    "case_no": "CaseNo",
    "registration_date": "CrimeRegisteredDate",   # expects YYYY-MM-DD
    "police_station_name": "PoliceStation",       # matched against Unit.UnitName — must match seeded station names
    "district_name": "District",                  # matched against District.DistrictName
    "crime_type_name": "CrimeType",                # matched against CrimeSubHead.CrimeHeadName
    "brief_facts": "BriefFacts",
    "accused_names": "AccusedNames",               # e.g. "Name1; Name2" — see _split_multi()
    "accused_ages": "AccusedAges",                 # e.g. "34; 28" — same order as accused_names
    "victim_names": "VictimNames",
    "victim_ages": "VictimAges",
}


def _split_multi(cell: str) -> list:
    """Adjust this if your file uses a different separator than ';' for
    multiple accused/victims in one cell."""
    if not cell:
        return []
    return [p.strip() for p in cell.split(";") if p.strip()]


def _lookup_station_id(conn, station_name: str, district_name: str):
    row = conn.execute(
        "SELECT u.UnitID FROM Unit u JOIN District d ON u.DistrictID=d.DistrictID "
        "WHERE u.UnitName=? AND d.DistrictName=?", (station_name, district_name)
    ).fetchone()
    return row[0] if row else None


def _lookup_crime_subhead_id(conn, crime_type_name: str):
    row = conn.execute("SELECT CrimeSubHeadID FROM CrimeSubHead WHERE CrimeHeadName=?",
                        (crime_type_name,)).fetchone()
    return row[0] if row else None


def build_confirmed_fields(conn, row: dict) -> dict:
    m = COLUMN_MAPPING
    station_id = _lookup_station_id(conn, row.get(m["police_station_name"], ""), row.get(m["district_name"], ""))
    if station_id is None:
        raise ValueError(f"Could not match police station '{row.get(m['police_station_name'])}' in district "
                          f"'{row.get(m['district_name'])}' to a seeded Unit — check spelling against the "
                          f"District/Unit names seed_reference_data() creates, or add the station there.")

    crime_subhead_id = _lookup_crime_subhead_id(conn, row.get(m["crime_type_name"], ""))

    accused_names = _split_multi(row.get(m["accused_names"], ""))
    accused_ages = _split_multi(row.get(m["accused_ages"], ""))
    accused = [{"name": n, "age": int(a) if a.isdigit() else None}
               for n, a in zip(accused_names, accused_ages + [None] * len(accused_names))]

    victim_names = _split_multi(row.get(m["victim_names"], ""))
    victim_ages = _split_multi(row.get(m["victim_ages"], ""))
    victims = [{"name": n, "age": int(a) if a.isdigit() else None}
               for n, a in zip(victim_names, victim_ages + [None] * len(victim_names))]

    return {
        "crime_no": row[m["crime_no"]],
        "case_no": row[m["case_no"]],
        "registration_date": row[m["registration_date"]],
        "police_station_id": station_id,
        "crime_minor_head_id": crime_subhead_id,
        "brief_facts": row.get(m["brief_facts"], ""),
        "accused": accused,
        "victims": victims,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", required=True, help="Path to your real dataset (CSV)")
    parser.add_argument("--confirm-wipe", action="store_true",
                         help="Required — acknowledges this DELETES the current database (including the "
                              "500 synthetic demo FIRs) before importing.")
    parser.add_argument("--dry-run", action="store_true",
                         help="Parse and validate every row against the schema without writing anything.")
    args = parser.parse_args()

    if not args.confirm_wipe:
        print("Refusing to run without --confirm-wipe (this deletes the current database first). "
              "Add --dry-run too if you just want to validate your file without writing anything.")
        sys.exit(1)

    if not args.dry_run:
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys=ON")
        create_schema(conn)
        seed_reference_data(conn)
        from brain import memory_engine
        import auth as _auth
        memory_engine.init_schema(conn)
        memory_engine.init_context_schema(conn)
        _auth.init_schema(conn)
        print(f"Schema + Karnataka reference data rebuilt at {DB_PATH}. Importing your real records now...")
    else:
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys=ON")
        create_schema(conn)
        seed_reference_data(conn)
        print("DRY RUN — validating your file against an in-memory schema copy; nothing will be written to disk.")

    imported, failed = 0, []
    with open(args.file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):  # row 1 is the header
            try:
                confirmed = build_confirmed_fields(conn, row)
            except (KeyError, ValueError) as e:
                failed.append((i, str(e)))
                continue
            if args.dry_run:
                imported += 1
                continue
            result = ingestion_engine.commit_draft(conn, confirmed, confirmed_by_employee_id=1)
            if result.get("success"):
                imported += 1
            else:
                failed.append((i, result.get("error")))

    print(f"\n{'Validated' if args.dry_run else 'Imported'}: {imported} row(s)")
    if failed:
        print(f"Failed: {len(failed)} row(s) — first 10 shown:")
        for row_num, err in failed[:10]:
            print(f"  Row {row_num}: {err}")
    if not args.dry_run:
        conn.close()


if __name__ == "__main__":
    main()
