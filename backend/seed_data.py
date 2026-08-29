"""
KAVACH Seed Data Generator — v2
===================================
Builds the database against the ACTUAL Karnataka State Police FIR
System ER diagram (CaseMaster, Accused, Victim, ComplainantDetails,
ArrestSurrender, Act/Section, CrimeHead/CrimeSubHead, and all the
lookup tables) — not a simplified stand-in schema.

On top of KSP's schema, this adds the "KAVACH Intelligence Layer":
tables that don't exist in the original ER diagram but are what make
the AI features possible — PersonIdentity (cross-case identity
resolution, built using brain/alias_resolver.py during seeding),
Phone/Vehicle/network link tables (for brain/graph_engine.py), and
the memory tables (for brain/memory_engine.py). These are clearly
namespaced and commented so it's obvious what's KSP's spec vs. what
KAVACH adds.

Run once: python seed_data.py
"""
import os
import random
import sqlite3
from datetime import datetime, timedelta

import sys
sys.path.insert(0, os.path.dirname(__file__))
from brain import alias_resolver, timeline_engine, mo_fingerprint

DB_PATH = os.getenv("DB_PATH", "kavach.db")
random.seed(42)  # reproducible demo data

# ═══════════════════════════════════════════════════════════════════════════
# REFERENCE DATA
# ═══════════════════════════════════════════════════════════════════════════

STATES = ["Karnataka", "Tamil Nadu", "Andhra Pradesh", "Kerala", "Maharashtra", "Goa"]

DISTRICTS = {
    "Bengaluru Urban":  ["Koramangala PS", "Whitefield PS", "Yelahanka PS", "Jayanagar PS",
                         "Indiranagar PS", "Rajajinagar PS", "Hebbal PS", "HSR Layout PS",
                         "Marathahalli PS", "JP Nagar PS"],
    "Bengaluru Rural":  ["Devanahalli PS", "Nelamangala PS", "Hosakote PS", "Doddaballapur PS"],
    "Mysuru":           ["Mysuru North PS", "Mysuru South PS", "Nanjangud PS", "Hunsur PS", "Chamarajanagar PS"],
    "Hubballi-Dharwad": ["Hubballi Rural PS", "Dharwad PS", "Kalghatgi PS", "Kundgol PS"],
    "Mangaluru":        ["Mangaluru Port PS", "Mangaluru North PS", "Bantwal PS", "Puttur PS"],
    "Belagavi":         ["Belagavi City PS", "Gokak PS", "Hukkeri PS", "Chikkodi PS"],
    "Kalaburagi":       ["Kalaburagi City PS", "Aland PS", "Yadgir PS", "Shorapur PS"],
    "Davanagere":       ["Davanagere City PS", "Channagiri PS", "Jagalur PS", "Harihar PS"],
    "Shivamogga":       ["Shivamogga City PS", "Sagara PS", "Soraba PS", "Thirthahalli PS"],
    "Tumakuru":         ["Tumakuru City PS", "Tiptur PS", "Kunigal PS", "Sira PS"],
    "Vijayapura":       ["Vijayapura City PS", "Sindagi PS", "Muddebihal PS", "Indi PS"],
    "Ballari":          ["Ballari City PS", "Sandur PS", "Hospete PS", "Siruguppa PS"],
}
GEO_BOUNDS = {
    "Bengaluru Urban": (12.85, 13.15, 77.45, 77.75), "Bengaluru Rural": (13.10, 13.40, 77.30, 77.80),
    "Mysuru": (11.90, 12.50, 76.40, 77.10), "Hubballi-Dharwad": (15.10, 15.60, 74.90, 75.40),
    "Mangaluru": (12.60, 13.10, 74.70, 75.40), "Belagavi": (15.60, 16.50, 74.30, 75.30),
    "Kalaburagi": (16.80, 17.50, 76.40, 77.50), "Davanagere": (14.20, 14.70, 75.50, 76.10),
    "Shivamogga": (13.70, 14.40, 74.80, 75.90), "Tumakuru": (13.10, 14.00, 76.70, 77.30),
    "Vijayapura": (16.50, 17.10, 75.50, 76.40), "Ballari": (14.80, 15.50, 76.40, 77.00),
}

RANKS = [
    ("Police Constable", 11), ("Head Constable", 10), ("Assistant Sub-Inspector", 9),
    ("Police Sub-Inspector", 8), ("Police Inspector", 7), ("Circle Police Inspector", 6),
    ("Deputy Superintendent of Police", 5), ("Superintendent of Police", 4),
    ("Deputy Inspector General", 3), ("Inspector General", 2), ("Director General of Police", 1),
]
DESIGNATIONS = ["Investigating Officer", "Station House Officer", "Beat Officer",
                "Cyber Cell Officer", "Traffic Officer", "Reserve Officer",
                "Circle Inspector", "District Superintendent"]

CASE_CATEGORIES = [("FIR", "1"), ("PAR", "4"), ("UDR", "3"), ("Zero FIR", "8")]
GRAVITY_LEVELS = ["Heinous", "Non-Heinous"]

CRIME_GROUPS = {
    "Crimes Against Body":        ["Murder", "Attempt to Murder", "Assault"],
    "Crimes Against Property":    ["Theft", "Burglary", "Robbery", "Dacoity", "Vehicle Theft", "Chain Snatching"],
    "Crimes Against Women":       ["Rape", "Domestic Violence"],
    "Economic Offences":          ["Fraud"],
    "Cyber Crimes":               ["Cybercrime"],
    "Narcotic Offences":          ["Drug Offense"],
}
SEVERITY = {"Murder": 10, "Dacoity": 9, "Rape": 10, "Attempt to Murder": 8, "Robbery": 7,
            "Drug Offense": 6, "Assault": 5, "Burglary": 5, "Fraud": 5, "Cybercrime": 5,
            "Domestic Violence": 5, "Vehicle Theft": 4, "Chain Snatching": 4, "Theft": 3}
CRIME_WEIGHT = {"Murder": 0.04, "Attempt to Murder": 0.05, "Robbery": 0.08, "Dacoity": 0.03,
                "Rape": 0.04, "Assault": 0.09, "Burglary": 0.09, "Theft": 0.14, "Vehicle Theft": 0.12,
                "Chain Snatching": 0.05, "Fraud": 0.07, "Drug Offense": 0.06, "Cybercrime": 0.06,
                "Domestic Violence": 0.04}

ACTS = [
    ("IPC", "Indian Penal Code", "IPC"), ("BNS", "Bharatiya Nyaya Sanhita", "BNS"),
    ("NDPS", "Narcotic Drugs and Psychotropic Substances Act", "NDPS"),
    ("POCSO", "Protection of Children from Sexual Offences Act", "POCSO"),
    ("IT_ACT", "Information Technology Act", "IT Act"), ("MV_ACT", "Motor Vehicles Act", "MV Act"),
]
SECTIONS = {
    "Murder": ("IPC", "302", "Murder"), "Attempt to Murder": ("IPC", "307", "Attempt to murder"),
    "Robbery": ("IPC", "392", "Robbery"), "Dacoity": ("IPC", "395", "Dacoity"),
    "Assault": ("IPC", "324", "Voluntarily causing hurt by dangerous weapons"),
    "Burglary": ("IPC", "454", "House-breaking"), "Theft": ("IPC", "379", "Theft"),
    "Vehicle Theft": ("IPC", "379", "Theft"), "Chain Snatching": ("IPC", "356", "Assault to commit theft"),
    "Fraud": ("IPC", "420", "Cheating"), "Rape": ("IPC", "376", "Rape"),
    "Domestic Violence": ("IPC", "498A", "Cruelty by husband or relatives"),
    "Drug Offense": ("NDPS", "20", "Contravention involving cannabis"),
    "Cybercrime": ("IT_ACT", "66", "Computer-related offences"),
}

CASTE_CATEGORIES = ["General", "OBC", "SC", "ST", "Category-1"]   # generic, schema-completeness only — never used in analytics
RELIGIONS = ["Hindu", "Muslim", "Christian", "Jain", "Buddhist", "Sikh", "Other"]
OCCUPATIONS = ["Auto Driver", "Construction Worker", "Farmer", "Daily Wage Labourer",
               "Small Trader", "Mechanic", "Carpenter", "Electrician", "Security Guard",
               "Street Vendor", "Unemployed", "Student", "Driver", "Hotel Worker",
               "Domestic Worker", "Tailor", "Plumber", "Painter", "Petty Shopkeeper",
               "Software Engineer", "Government Employee"]
EDUCATIONS = ["Illiterate", "Primary School", "High School", "PUC", "Diploma", "Graduate"]
CASE_STATUSES = ["Under Investigation", "Charge-Sheeted", "Closed", "Undetected"]

MALE_FIRST = ["Ramesh", "Suresh", "Mahesh", "Raju", "Krishna", "Ganesh", "Manjunath",
              "Venkatesha", "Basavanna", "Siddaraju", "Prakash", "Nagaraj", "Shivakumar",
              "Lokesh", "Mahadeva", "Rajesh", "Arun", "Deepak", "Santosh", "Girish",
              "Ashok", "Vijay", "Anand", "Kiran", "Mohan", "Ibrahim", "Mohammed",
              "Ashraf", "Siddique", "Joseph", "Thomas", "Anthony", "Vinod", "Prasad",
              "Harish", "Umesh", "Naveen", "Srinivas", "Dinesh", "Shivaraj"]
FEMALE_FIRST = ["Kavitha", "Suma", "Latha", "Meena", "Pushpa", "Shantha", "Vijaya",
                "Indira", "Savitha", "Radha", "Usha", "Geetha", "Anitha", "Prema",
                "Rekha", "Saroja", "Mamatha", "Sharada", "Nirmala", "Sunitha",
                "Fatima", "Ayesha", "Mary", "Rosemary", "Lakshmi", "Parvathi"]
SURNAMES = ["Gowda", "Naik", "Reddy", "Patil", "Rao", "Hegde", "Shetty", "Nayak",
            "Poojary", "Kamath", "Bhat", "Joshi", "Kulkarni", "Desai", "Naidu",
            "Swamy", "Murthy", "Raju", "Kumar", "Babu", "Prasad", "Iyer",
            "Patel", "Shah", "Khan", "Shaikh", "D'Souza", "Fernandes", "Pereira"]

MODUS_OPERANDI = [
    "Operates in early morning hours, targets parked vehicles, flees on the same motorbike",
    "Poses as delivery personnel to gain entry, uses a knife to threaten occupants",
    "Uses stolen vehicles as getaway after chain snatching near markets",
    "Targets elderly victims at ATM counters, works alone, on foot",
    "Creates distraction while accomplice pickpockets in crowded buses",
    "Uses online fraud through fake loan apps, requests OTP via phone call",
    "Uses a knife as weapon, targets isolated victims at night, escapes on foot",
    "Peddles drugs near educational institutions, uses two-wheeler for quick delivery",
    "Breaks into houses when family is away for festivals, enters via rear window",
    "Targets jewellery shops just before closing time, uses firearm",
    "Operates in a gang of 3-4, uses motorbikes for quick escape after robbery",
    "Runs cyber fraud through UPI and OTP phishing calls",
]
FIR_DESCRIPTIONS = {
    "Murder": ["Deceased found with multiple stab wounds at residence following an argument.",
               "Victim allegedly beaten to death following a land dispute."],
    "Robbery": ["Armed gang robbed cash and gold jewellery from complainant near the market.",
                "Two accused on motorbike snatched the bag of the complainant."],
    "Vehicle Theft": ["Complainant's two-wheeler stolen from the parking area outside the apartment.",
                       "Car found missing from premises; CCTV shows suspects tampering with the lock."],
    "Theft": ["Cash and valuables worth Rs. 45,000 stolen while the family was away.",
              "Mobile phone and wallet stolen from complainant's bag in a crowded bus."],
    "Cybercrime": ["Complainant received a call posing as bank officials and was duped via UPI.",
                    "Accused created a fake investment app and collected money before disappearing."],
    "Drug Offense": ["Contraband seized from accused acting on tip-off from a confidential informant.",
                      "Inter-state drug supply network busted, contraband concealed in commercial goods."],
    "Assault": ["Complainant assaulted with an iron rod following a parking dispute.",
                "Complainant attacked by neighbour over a property boundary dispute."],
    "Burglary": ["Door lock broken, cash and electronics worth Rs. 1.2 lakhs stolen.",
                 "Office premises broken into at night; CCTV DVR and cash stolen."],
    "Fraud": ["Complainant duped of Rs. 12 lakhs by accused posing as a real estate agent.",
              "Chit fund fraud — accused collected money from 45 members and absconded."],
    "Chain Snatching": ["Two persons on motorbike snatched a gold chain near the market junction."],
    "Domestic Violence": ["Complainant alleges physical and mental harassment by husband over dowry."],
    "Attempt to Murder": ["Complainant attacked with a sharp weapon following a financial dispute."],
    "Dacoity": ["Five armed persons entered the shop, held staff at gunpoint, robbed cash."],
    "Rape": ["Victim filed complaint alleging sexual assault by an accused known to her family."],
}

# ═══════════════════════════════════════════════════════════════════════════
# SCHEMA — matches KSP's ER diagram, plus the KAVACH Intelligence Layer
# ═══════════════════════════════════════════════════════════════════════════

def create_schema(conn):
    conn.executescript("""
    PRAGMA foreign_keys = ON;

    -- ─── KSP reference / lookup tables ────────────────────────────────────
    CREATE TABLE State (
        StateID INTEGER PRIMARY KEY AUTOINCREMENT, StateName TEXT NOT NULL,
        NationalityID INTEGER DEFAULT 1, Active INTEGER DEFAULT 1
    );
    CREATE TABLE District (
        DistrictID INTEGER PRIMARY KEY AUTOINCREMENT, DistrictName TEXT NOT NULL,
        StateID INTEGER REFERENCES State(StateID), Active INTEGER DEFAULT 1
    );
    CREATE TABLE UnitType (
        UnitTypeID INTEGER PRIMARY KEY AUTOINCREMENT, UnitTypeName TEXT NOT NULL,
        CityDistState TEXT, Hierarchy INTEGER, Active INTEGER DEFAULT 1
    );
    CREATE TABLE Unit (
        UnitID INTEGER PRIMARY KEY AUTOINCREMENT, UnitName TEXT NOT NULL,
        TypeID INTEGER REFERENCES UnitType(UnitTypeID), ParentUnit INTEGER,
        NationalityID INTEGER DEFAULT 1, StateID INTEGER REFERENCES State(StateID),
        DistrictID INTEGER REFERENCES District(DistrictID), Active INTEGER DEFAULT 1
    );
    CREATE TABLE Rank (
        RankID INTEGER PRIMARY KEY AUTOINCREMENT, RankName TEXT NOT NULL,
        Hierarchy INTEGER, Active INTEGER DEFAULT 1
    );
    CREATE TABLE Designation (
        DesignationID INTEGER PRIMARY KEY AUTOINCREMENT, DesignationName TEXT NOT NULL,
        Active INTEGER DEFAULT 1, SortOrder INTEGER
    );
    CREATE TABLE Employee (
        EmployeeID INTEGER PRIMARY KEY AUTOINCREMENT,
        DistrictID INTEGER REFERENCES District(DistrictID), UnitID INTEGER REFERENCES Unit(UnitID),
        RankID INTEGER REFERENCES Rank(RankID), DesignationID INTEGER REFERENCES Designation(DesignationID),
        KGID TEXT, FirstName TEXT NOT NULL, EmployeeDOB TEXT, GenderID TEXT,
        BloodGroupID TEXT, PhysicallyChallenged INTEGER DEFAULT 0, AppointmentDate TEXT
    );
    CREATE TABLE CaseCategory (
        CaseCategoryID INTEGER PRIMARY KEY AUTOINCREMENT, LookupValue TEXT NOT NULL, CategoryCode TEXT
    );
    CREATE TABLE GravityOffence (
        GravityOffenceID INTEGER PRIMARY KEY AUTOINCREMENT, LookupValue TEXT NOT NULL
    );
    CREATE TABLE CrimeHead (
        CrimeHeadID INTEGER PRIMARY KEY AUTOINCREMENT, CrimeGroupName TEXT NOT NULL, Active INTEGER DEFAULT 1
    );
    CREATE TABLE CrimeSubHead (
        CrimeSubHeadID INTEGER PRIMARY KEY AUTOINCREMENT,
        CrimeHeadID INTEGER REFERENCES CrimeHead(CrimeHeadID), CrimeHeadName TEXT NOT NULL, SeqID INTEGER
    );
    CREATE TABLE Act (
        ActCode TEXT PRIMARY KEY, ActDescription TEXT NOT NULL, ShortName TEXT, Active INTEGER DEFAULT 1
    );
    CREATE TABLE Section (
        ActCode TEXT REFERENCES Act(ActCode), SectionCode TEXT,
        SectionDescription TEXT, Active INTEGER DEFAULT 1, PRIMARY KEY (ActCode, SectionCode)
    );
    CREATE TABLE CrimeHeadActSection (
        CrimeHeadID INTEGER REFERENCES CrimeHead(CrimeHeadID), ActCode TEXT, SectionCode TEXT
    );
    CREATE TABLE CasteMaster (
        caste_master_id INTEGER PRIMARY KEY AUTOINCREMENT, caste_master_name TEXT NOT NULL
    );
    CREATE TABLE ReligionMaster (
        ReligionID INTEGER PRIMARY KEY AUTOINCREMENT, ReligionName TEXT NOT NULL
    );
    CREATE TABLE OccupationMaster (
        OccupationID INTEGER PRIMARY KEY AUTOINCREMENT, OccupationName TEXT NOT NULL
    );
    CREATE TABLE CaseStatusMaster (
        CaseStatusID INTEGER PRIMARY KEY AUTOINCREMENT, CaseStatusName TEXT NOT NULL
    );
    CREATE TABLE Court (
        CourtID INTEGER PRIMARY KEY AUTOINCREMENT, CourtName TEXT NOT NULL,
        DistrictID INTEGER REFERENCES District(DistrictID), StateID INTEGER REFERENCES State(StateID),
        Active INTEGER DEFAULT 1
    );

    -- ─── KSP core transactional tables ────────────────────────────────────
    CREATE TABLE CaseMaster (
        CaseMasterID INTEGER PRIMARY KEY AUTOINCREMENT, CrimeNo TEXT UNIQUE NOT NULL, CaseNo TEXT NOT NULL,
        CrimeRegisteredDate TEXT NOT NULL, PolicePersonID INTEGER REFERENCES Employee(EmployeeID),
        PoliceStationID INTEGER REFERENCES Unit(UnitID), CaseCategoryID INTEGER REFERENCES CaseCategory(CaseCategoryID),
        GravityOffenceID INTEGER REFERENCES GravityOffence(GravityOffenceID),
        CrimeMajorHeadID INTEGER REFERENCES CrimeHead(CrimeHeadID),
        CrimeMinorHeadID INTEGER REFERENCES CrimeSubHead(CrimeSubHeadID),
        CaseStatusID INTEGER REFERENCES CaseStatusMaster(CaseStatusID), CourtID INTEGER REFERENCES Court(CourtID),
        IncidentFromDate TEXT, IncidentToDate TEXT, InfoReceivedPSDate TEXT,
        latitude REAL, longitude REAL, BriefFacts TEXT,
        OccurrenceTime TEXT, WeaponUsed TEXT, VehicleInvolved TEXT, OffenderCount INTEGER DEFAULT 1
        -- last 4 columns are KAVACH extensions (not in the base ER diagram) —
        -- needed for brain/similarity_engine.py and brain/mo_fingerprint.py
    );
    CREATE TABLE ComplainantDetails (
        ComplainantID INTEGER PRIMARY KEY AUTOINCREMENT, CaseMasterID INTEGER REFERENCES CaseMaster(CaseMasterID),
        ComplainantName TEXT NOT NULL, AgeYear INTEGER, OccupationID INTEGER REFERENCES OccupationMaster(OccupationID),
        ReligionID INTEGER REFERENCES ReligionMaster(ReligionID), CasteID INTEGER REFERENCES CasteMaster(caste_master_id),
        GenderID TEXT
    );
    CREATE TABLE ActSectionAssociation (
        CaseMasterID INTEGER REFERENCES CaseMaster(CaseMasterID), ActID TEXT, SectionID TEXT,
        ActOrderID INTEGER, SectionOrderID INTEGER
    );
    CREATE TABLE Victim (
        VictimMasterID INTEGER PRIMARY KEY AUTOINCREMENT, CaseMasterID INTEGER REFERENCES CaseMaster(CaseMasterID),
        VictimName TEXT NOT NULL, AgeYear INTEGER, GenderID TEXT, VictimPolice INTEGER DEFAULT 0
    );
    CREATE TABLE Accused (
        AccusedMasterID INTEGER PRIMARY KEY AUTOINCREMENT, CaseMasterID INTEGER REFERENCES CaseMaster(CaseMasterID),
        AccusedName TEXT NOT NULL, AgeYear INTEGER, GenderID TEXT, PersonID TEXT,
        FatherOrSpouseName TEXT   -- KAVACH extension: real Indian identity-verification field, absent from the base ER diagram
    );
    CREATE TABLE ArrestSurrender (
        ArrestSurrenderID INTEGER PRIMARY KEY AUTOINCREMENT, CaseMasterID INTEGER REFERENCES CaseMaster(CaseMasterID),
        ArrestSurrenderTypeID INTEGER, ArrestSurrenderDate TEXT,
        ArrestSurrenderStateId INTEGER REFERENCES State(StateID), ArrestSurrenderDistrictId INTEGER REFERENCES District(DistrictID),
        PoliceStationID INTEGER REFERENCES Unit(UnitID), IOID INTEGER REFERENCES Employee(EmployeeID),
        CourtID INTEGER REFERENCES Court(CourtID), AccusedMasterID INTEGER REFERENCES Accused(AccusedMasterID),
        IsAccused INTEGER DEFAULT 1, IsComplainantAccused INTEGER DEFAULT 0, BailStatus TEXT DEFAULT 'None'
    );
    CREATE TABLE ChargesheetDetails (
        CSID INTEGER PRIMARY KEY AUTOINCREMENT, CaseMasterID INTEGER REFERENCES CaseMaster(CaseMasterID),
        csdate TEXT, cstype TEXT, PolicePersonID INTEGER REFERENCES Employee(EmployeeID)
    );

    -- ─── KAVACH Intelligence Layer (extends KSP's schema, clearly namespaced) ──
    CREATE TABLE CaseFinancialImpact (
        CaseMasterID INTEGER PRIMARY KEY REFERENCES CaseMaster(CaseMasterID), EstimatedLossValue REAL
    );
    CREATE TABLE InvestigationUpdate (
        UpdateID INTEGER PRIMARY KEY AUTOINCREMENT, CaseMasterID INTEGER REFERENCES CaseMaster(CaseMasterID),
        UpdateDate TEXT, UpdateText TEXT, OfficerName TEXT, Stage TEXT
    );
    CREATE TABLE PersonIdentity (
        PersonIdentityID INTEGER PRIMARY KEY AUTOINCREMENT, CanonicalName TEXT NOT NULL, PrimaryAlias TEXT,
        AgeYear INTEGER, GenderID TEXT, DistrictID INTEGER REFERENCES District(DistrictID),
        OccupationID INTEGER REFERENCES OccupationMaster(OccupationID), EducationLevel TEXT,
        RiskScore REAL DEFAULT 0, RiskCategory TEXT DEFAULT 'LOW', ModusOperandi TEXT,
        GangAffiliation TEXT, IsRepeatOffender INTEGER DEFAULT 0, PhoneNumber TEXT, FatherOrSpouseName TEXT
    );
    CREATE TABLE PersonIdentityLink (
        LinkID INTEGER PRIMARY KEY AUTOINCREMENT, PersonIdentityID INTEGER REFERENCES PersonIdentity(PersonIdentityID),
        AccusedMasterID INTEGER REFERENCES Accused(AccusedMasterID), MatchConfidence REAL, MatchMethod TEXT
    );
    CREATE TABLE Phone (
        PhoneID INTEGER PRIMARY KEY AUTOINCREMENT, PhoneNumber TEXT UNIQUE NOT NULL
    );
    CREATE TABLE PersonPhoneLink (
        PersonIdentityID INTEGER REFERENCES PersonIdentity(PersonIdentityID), PhoneID INTEGER REFERENCES Phone(PhoneID)
    );
    CREATE TABLE PhoneCallLink (
        FromPhoneID INTEGER REFERENCES Phone(PhoneID), ToPhoneID INTEGER REFERENCES Phone(PhoneID),
        CallDate TEXT, DurationSeconds INTEGER
    );
    CREATE TABLE Vehicle (
        VehicleID INTEGER PRIMARY KEY AUTOINCREMENT, RegistrationNumber TEXT UNIQUE NOT NULL, VehicleType TEXT
    );
    CREATE TABLE PersonVehicleLink (
        PersonIdentityID INTEGER REFERENCES PersonIdentity(PersonIdentityID), VehicleID INTEGER REFERENCES Vehicle(VehicleID)
    );
    CREATE TABLE VehicleSighting (
        VehicleID INTEGER REFERENCES Vehicle(VehicleID), CaseMasterID INTEGER REFERENCES CaseMaster(CaseMasterID)
    );
    CREATE TABLE PersonNetworkLink (
        LinkID INTEGER PRIMARY KEY AUTOINCREMENT,
        PersonIdentityID_A INTEGER REFERENCES PersonIdentity(PersonIdentityID),
        PersonIdentityID_B INTEGER REFERENCES PersonIdentity(PersonIdentityID),
        RelationshipType TEXT, Strength REAL DEFAULT 0.5, Notes TEXT
    );
    CREATE TABLE CrimeTrend (
        TrendID INTEGER PRIMARY KEY AUTOINCREMENT, Year INTEGER, Month INTEGER,
        DistrictID INTEGER REFERENCES District(DistrictID), CrimeSubHeadID INTEGER REFERENCES CrimeSubHead(CrimeSubHeadID),
        CaseCount INTEGER DEFAULT 0, ArrestCount INTEGER DEFAULT 0
    );
    CREATE TABLE Users (
        UserID INTEGER PRIMARY KEY AUTOINCREMENT, Username TEXT UNIQUE NOT NULL, PasswordHash TEXT NOT NULL,
        EmployeeID INTEGER REFERENCES Employee(EmployeeID), Role TEXT NOT NULL, IsActive INTEGER DEFAULT 1
    );

    -- ─── Flattened views — simplify every downstream query in sql_builder.py ──
    CREATE VIEW vw_fir_flat AS
    SELECT
        cm.CaseMasterID AS fir_id, cm.CrimeNo AS fir_number, cm.CaseNo AS case_no,
        cm.CrimeRegisteredDate AS registration_date, cm.IncidentFromDate AS occurrence_date,
        d.DistrictName AS district, u.UnitName AS police_station,
        csh.CrimeHeadName AS crime_type, ch.CrimeGroupName AS crime_group,
        csm.CaseStatusName AS status, cm.latitude, cm.longitude, cm.BriefFacts AS crime_description,
        go.LookupValue AS gravity, emp.FirstName AS investigating_officer,
        cfi.EstimatedLossValue AS property_value, cc.LookupValue AS case_category,
        cm.OccurrenceTime AS occurrence_time, cm.WeaponUsed AS weapon_used,
        cm.VehicleInvolved AS vehicle_involved, cm.OffenderCount AS offender_count
    FROM CaseMaster cm
    LEFT JOIN Unit u ON cm.PoliceStationID = u.UnitID
    LEFT JOIN District d ON u.DistrictID = d.DistrictID
    LEFT JOIN CrimeSubHead csh ON cm.CrimeMinorHeadID = csh.CrimeSubHeadID
    LEFT JOIN CrimeHead ch ON cm.CrimeMajorHeadID = ch.CrimeHeadID
    LEFT JOIN CaseStatusMaster csm ON cm.CaseStatusID = csm.CaseStatusID
    LEFT JOIN GravityOffence go ON cm.GravityOffenceID = go.GravityOffenceID
    LEFT JOIN Employee emp ON cm.PolicePersonID = emp.EmployeeID
    LEFT JOIN CaseFinancialImpact cfi ON cm.CaseMasterID = cfi.CaseMasterID
    LEFT JOIN CaseCategory cc ON cm.CaseCategoryID = cc.CaseCategoryID;

    CREATE VIEW vw_person_flat AS
    SELECT
        pi.PersonIdentityID AS person_id, pi.CanonicalName AS name, pi.PrimaryAlias AS alias,
        pi.AgeYear AS age, pi.GenderID AS gender, d.DistrictName AS district,
        om.OccupationName AS occupation, pi.EducationLevel AS education,
        pi.RiskScore AS risk_score, pi.RiskCategory AS risk_category, pi.ModusOperandi AS modus_operandi,
        pi.GangAffiliation AS gang_affiliation, pi.IsRepeatOffender AS is_repeat_offender,
        pi.PhoneNumber AS phone, pi.FatherOrSpouseName AS father_or_spouse_name,
        (SELECT COUNT(*) FROM PersonIdentityLink pil WHERE pil.PersonIdentityID = pi.PersonIdentityID) AS prior_convictions
    FROM PersonIdentity pi
    LEFT JOIN District d ON pi.DistrictID = d.DistrictID
    LEFT JOIN OccupationMaster om ON pi.OccupationID = om.OccupationID;
    """)
    conn.commit()
    print("✅ Schema created (KSP-compliant core + KAVACH Intelligence Layer + views)")


# ═══════════════════════════════════════════════════════════════════════════
# SEEDING — REFERENCE DATA
# ═══════════════════════════════════════════════════════════════════════════

def seed_reference_data(conn):
    """Seeds every lookup table and returns a dict of name->id maps used
    by every later seeding step."""
    L = {}  # lookups

    L["state"] = {}
    for s in STATES:
        cur = conn.execute("INSERT INTO State (StateName) VALUES (?)", (s,))
        L["state"][s] = cur.lastrowid

    L["district"] = {}
    for d in DISTRICTS:
        cur = conn.execute("INSERT INTO District (DistrictName, StateID) VALUES (?,?)",
                            (d, L["state"]["Karnataka"]))
        L["district"][d] = cur.lastrowid

    cur = conn.execute("INSERT INTO UnitType (UnitTypeName, CityDistState, Hierarchy) VALUES (?,?,?)",
                        ("Police Station", "City", 3))
    ps_type_id = cur.lastrowid
    conn.execute("INSERT INTO UnitType (UnitTypeName, CityDistState, Hierarchy) VALUES (?,?,?)",
                 ("District SP Office", "District", 2))

    L["unit"] = {}
    for district, stations in DISTRICTS.items():
        for station in stations:
            cur = conn.execute(
                "INSERT INTO Unit (UnitName, TypeID, StateID, DistrictID) VALUES (?,?,?,?)",
                (station, ps_type_id, L["state"]["Karnataka"], L["district"][district])
            )
            L["unit"][station] = cur.lastrowid

    L["rank"] = {}
    for name, hierarchy in RANKS:
        cur = conn.execute("INSERT INTO Rank (RankName, Hierarchy) VALUES (?,?)", (name, hierarchy))
        L["rank"][name] = cur.lastrowid

    L["designation"] = {}
    for i, d in enumerate(DESIGNATIONS):
        cur = conn.execute("INSERT INTO Designation (DesignationName, SortOrder) VALUES (?,?)", (d, i))
        L["designation"][d] = cur.lastrowid

    L["employee"] = []
    officer_names = ["Ramesh Gowda", "Priya Nayak", "Suresh Patil", "Anita Reddy",
                      "Mohammed Ashfaq", "Deepak Kumar", "Kavitha Shetty", "Nagaraj Bhat",
                      "Vijay Desai", "Sunitha Rao", "Manjunath Iyer", "Lakshmi Hegde"]
    for name in officer_names:
        district = random.choice(list(DISTRICTS.keys()))
        unit = random.choice(DISTRICTS[district])
        cur = conn.execute(
            """INSERT INTO Employee (DistrictID, UnitID, RankID, DesignationID, KGID, FirstName,
                                      EmployeeDOB, GenderID, AppointmentDate)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (L["district"][district], L["unit"][unit],
             L["rank"][random.choice(["Police Sub-Inspector", "Police Inspector", "Circle Police Inspector"])],
             L["designation"][random.choice(DESIGNATIONS)],
             f"KGID{random.randint(10000,99999)}", name,
             f"{random.randint(1970,1990)}-0{random.randint(1,9)}-{random.randint(10,28)}",
             "F" if name.split()[0] in FEMALE_FIRST else "M",
             f"{random.randint(2000,2015)}-01-01")
        )
        L["employee"].append({"id": cur.lastrowid, "name": name, "district": district})

    L["case_category"] = {}
    for name, code in CASE_CATEGORIES:
        cur = conn.execute("INSERT INTO CaseCategory (LookupValue, CategoryCode) VALUES (?,?)", (name, code))
        L["case_category"][name] = {"id": cur.lastrowid, "code": code}

    L["gravity"] = {}
    for g in GRAVITY_LEVELS:
        cur = conn.execute("INSERT INTO GravityOffence (LookupValue) VALUES (?)", (g,))
        L["gravity"][g] = cur.lastrowid

    L["crime_head"] = {}
    L["crime_subhead"] = {}
    for group, subtypes in CRIME_GROUPS.items():
        cur = conn.execute("INSERT INTO CrimeHead (CrimeGroupName) VALUES (?)", (group,))
        head_id = cur.lastrowid
        L["crime_head"][group] = head_id
        for i, sub in enumerate(subtypes):
            cur2 = conn.execute("INSERT INTO CrimeSubHead (CrimeHeadID, CrimeHeadName, SeqID) VALUES (?,?,?)",
                                 (head_id, sub, i))
            L["crime_subhead"][sub] = {"id": cur2.lastrowid, "head_id": head_id, "head_name": group}

    for code, desc, short in ACTS:
        conn.execute("INSERT INTO Act (ActCode, ActDescription, ShortName) VALUES (?,?,?)", (code, desc, short))

    for crime, (act, section, desc) in SECTIONS.items():
        conn.execute("INSERT OR IGNORE INTO Section (ActCode, SectionCode, SectionDescription) VALUES (?,?,?)",
                     (act, section, desc))
        if crime in L["crime_subhead"]:
            conn.execute("INSERT INTO CrimeHeadActSection (CrimeHeadID, ActCode, SectionCode) VALUES (?,?,?)",
                         (L["crime_subhead"][crime]["head_id"], act, section))

    L["caste"] = {}
    for c in CASTE_CATEGORIES:
        cur = conn.execute("INSERT INTO CasteMaster (caste_master_name) VALUES (?)", (c,))
        L["caste"][c] = cur.lastrowid

    L["religion"] = {}
    for r in RELIGIONS:
        cur = conn.execute("INSERT INTO ReligionMaster (ReligionName) VALUES (?)", (r,))
        L["religion"][r] = cur.lastrowid

    L["occupation"] = {}
    for o in OCCUPATIONS:
        cur = conn.execute("INSERT INTO OccupationMaster (OccupationName) VALUES (?)", (o,))
        L["occupation"][o] = cur.lastrowid

    L["case_status"] = {}
    for s in CASE_STATUSES:
        cur = conn.execute("INSERT INTO CaseStatusMaster (CaseStatusName) VALUES (?)", (s,))
        L["case_status"][s] = cur.lastrowid

    L["court"] = {}
    for district in DISTRICTS:
        cur = conn.execute("INSERT INTO Court (CourtName, DistrictID, StateID) VALUES (?,?,?)",
                            (f"{district} District & Sessions Court", L["district"][district], L["state"]["Karnataka"]))
        L["court"][district] = cur.lastrowid

    # Demo login users — REAL bcrypt-hashed passwords, not a placeholder.
    # Credentials are printed at the end of seeding so the team has them.
    import auth as _auth
    demo_users = [
        ("investigator1", "Kavach@2026", "Ramesh Gowda", "investigator"),
        ("analyst1", "Kavach@2026", "Kavitha Shetty", "analyst"),
        ("supervisor1", "Kavach@2026", "Nagaraj Bhat", "supervisor"),
        ("admin", "Kavach@2026", "Vijay Desai", "admin"),
    ]
    emp_by_name = {e["name"]: e["id"] for e in L["employee"]}
    for username, password, emp_name, role in demo_users:
        conn.execute("INSERT INTO Users (Username, PasswordHash, EmployeeID, Role) VALUES (?,?,?,?)",
                     (username, _auth.hash_password(password), emp_by_name.get(emp_name), role))

    conn.commit()
    print(f"✅ Reference data seeded: {len(L['district'])} districts, {len(L['unit'])} units, "
          f"{len(L['employee'])} officers, {len(L['crime_subhead'])} crime types")
    return L


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def rand_date(start_year=2021, end_year=2026):
    start, end = datetime(start_year, 1, 1), datetime(min(end_year, 2026), 6, 30)
    delta = (end - start).days
    return (start + timedelta(days=random.randint(0, max(delta, 1)))).strftime("%Y-%m-%d")

def rand_time():
    return f"{random.randint(0,23):02d}:{random.choice([0,15,30,45]):02d}"

def rand_name(gender="M"):
    first = random.choice(MALE_FIRST if gender == "M" else FEMALE_FIRST)
    return f"{first} {random.choice(SURNAMES)}"

def rand_coords(district):
    lat_min, lat_max, lng_min, lng_max = GEO_BOUNDS.get(district, (12.9, 13.0, 77.5, 77.6))
    return round(random.uniform(lat_min, lat_max), 5), round(random.uniform(lng_min, lng_max), 5)

def pick_crime():
    types, weights = zip(*CRIME_WEIGHT.items())
    return random.choices(types, weights=weights, k=1)[0]

WEAPONS = ["Knife", "Iron Rod", "Stone", "Firearm", None, None, None, None]
VEHICLES = ["Two-Wheeler", "Car", "Auto", None, None, None]


class Counters:
    """Per-(unit,category,year) running serial — matches KSP's CrimeNo spec exactly."""
    def __init__(self):
        self.c = {}
    def next_serial(self, unit_id, category_code, year):
        key = (unit_id, category_code, year)
        self.c[key] = self.c.get(key, 0) + 1
        return self.c[key]


def build_crime_no(category_code, district_id, unit_id, year, serial):
    return f"{category_code}{district_id:04d}{unit_id:04d}{year}{serial:05d}"


# ═══════════════════════════════════════════════════════════════════════════
# SEEDING — CASES (CaseMaster, ComplainantDetails, ActSectionAssociation, Victim)
# ═══════════════════════════════════════════════════════════════════════════

def seed_cases(conn, L, count=500):
    counters = Counters()
    cases = []

    for i in range(count):
        district = random.choice(list(DISTRICTS.keys()))
        station = random.choice(DISTRICTS[district])
        crime = pick_crime()
        reg_date = rand_date()
        year = int(reg_date[:4])
        category_name = "FIR" if random.random() > 0.08 else random.choice(["UDR", "PAR", "Zero FIR"])
        category = L["case_category"][category_name]
        district_id, unit_id = L["district"][district], L["unit"][station]
        serial = counters.next_serial(unit_id, category["code"], year)
        crime_no = build_crime_no(category["code"], district_id, unit_id, year, serial)
        case_no = f"{year}{serial:05d}"

        lat, lng = rand_coords(district)
        status = random.choice(CASE_STATUSES[:1] * 4 + CASE_STATUSES[1:])  # weight toward "Under Investigation"
        subhead = L["crime_subhead"][crime]
        officer = random.choice([e for e in L["employee"]])
        act, section, _ = SECTIONS.get(crime, ("IPC", "000", ""))
        offender_count = random.choices([1, 2, 3, 4], weights=[0.5, 0.28, 0.14, 0.08])[0]

        cur = conn.execute(
            """INSERT INTO CaseMaster
               (CrimeNo, CaseNo, CrimeRegisteredDate, PolicePersonID, PoliceStationID, CaseCategoryID,
                GravityOffenceID, CrimeMajorHeadID, CrimeMinorHeadID, CaseStatusID, CourtID,
                IncidentFromDate, InfoReceivedPSDate, latitude, longitude, BriefFacts,
                OccurrenceTime, WeaponUsed, VehicleInvolved, OffenderCount)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (crime_no, case_no, reg_date, officer["id"], unit_id, category["id"],
             L["gravity"]["Heinous" if SEVERITY.get(crime, 3) >= 7 else "Non-Heinous"],
             subhead["head_id"], subhead["id"], L["case_status"][status], L["court"][district],
             reg_date, reg_date, lat, lng,
             random.choice(FIR_DESCRIPTIONS.get(crime, ["Complaint registered. Investigation underway."])),
             rand_time(), random.choice(WEAPONS), random.choice(VEHICLES), offender_count)
        )
        case_id = cur.lastrowid

        conn.execute("INSERT INTO ActSectionAssociation (CaseMasterID, ActID, SectionID, ActOrderID, SectionOrderID) VALUES (?,?,?,1,1)",
                     (case_id, act, section))

        # ComplainantDetails — religion/caste captured for schema fidelity only,
        # NEVER read by any analytics or risk-scoring code in this project
        gender = random.choice(["M", "M", "F"])
        conn.execute(
            """INSERT INTO ComplainantDetails (CaseMasterID, ComplainantName, AgeYear, OccupationID, ReligionID, CasteID, GenderID)
               VALUES (?,?,?,?,?,?,?)""",
            (case_id, rand_name(gender), random.randint(18, 70), L["occupation"][random.choice(OCCUPATIONS)],
             L["religion"][random.choice(RELIGIONS)], L["caste"][random.choice(CASTE_CATEGORIES)], gender)
        )

        # Victim
        vgender = random.choice(["M", "M", "F"])
        conn.execute("INSERT INTO Victim (CaseMasterID, VictimName, AgeYear, GenderID) VALUES (?,?,?,?)",
                     (case_id, rand_name(vgender), random.randint(10, 75), vgender))

        # Financial impact (KAVACH extension) for property-relevant crimes
        if crime in ("Theft", "Robbery", "Burglary", "Vehicle Theft", "Fraud", "Chain Snatching", "Dacoity"):
            conn.execute("INSERT INTO CaseFinancialImpact (CaseMasterID, EstimatedLossValue) VALUES (?,?)",
                         (case_id, round(random.uniform(2000, 500000), 2)))

        cases.append({
            "id": case_id, "crime_no": crime_no, "district": district, "district_id": district_id,
            "station": station, "unit_id": unit_id, "crime_type": crime, "reg_date": reg_date,
            "status": status, "offender_count": offender_count,
        })

    conn.commit()
    print(f"✅ Seeded {count} cases (CaseMaster + Complainant + ActSection + Victim + FinancialImpact)")
    return cases


# ═══════════════════════════════════════════════════════════════════════════
# SEEDING — ACCUSED (raw, per-case — deliberately includes name-spelling
# variance across cases, so identity clustering has real work to do)
# ═══════════════════════════════════════════════════════════════════════════

def _build_recurring_identity_pool(L, n=24):
    """
    A fixed pool of 'real' repeat offenders, each with a canonical name,
    a father/spouse name, a fixed age and district — and a set of name
    SPELLING VARIANTS (drawn straight from alias_resolver's dictionary,
    plus a couple of raw fuzzy-typo variants) that different FIRs will
    use when referring to the same person. This is what gives
    cluster_identities() real signal to work with, instead of a toy demo.
    """
    canon_pool = list(alias_resolver.KANNADA_NAME_ALIASES.keys())
    random.shuffle(canon_pool)
    pool = []
    for canon in canon_pool[:n]:
        surname = random.choice(SURNAMES)
        variants = [canon.title()] + [a.title() for a in alias_resolver.KANNADA_NAME_ALIASES[canon]]
        full_variants = [f"{v} {surname}" for v in variants] + [v for v in variants]  # with & without surname
        district = random.choice(list(DISTRICTS.keys()))
        pool.append({
            "canonical": f"{canon.title()} {surname}",
            "variants": full_variants,
            "father_name": f"{random.choice(MALE_FIRST)} {surname}",
            "age": random.randint(22, 48),
            "gender": "M",
            "district": district,
            "case_ids": [],  # filled in as we assign this identity to cases
        })
    return pool


def seed_accused(conn, L, cases):
    identity_pool = _build_recurring_identity_pool(L, n=24)
    raw_accused = []   # every per-case Accused row, for later clustering
    person_counter = {}  # case_id -> next PersonID letter index

    for case in cases:
        n_accused = case["offender_count"]
        same_district_identities = [p for p in identity_pool if p["district"] == case["district"]]
        identities_used_this_case = set()  # prevents "Manju" and "Manja" both being listed
                                            # as separate accused in the SAME FIR — unrealistic

        for idx in range(n_accused):
            available = [p for p in same_district_identities if id(p) not in identities_used_this_case]
            use_recurring = available and random.random() < 0.35
            if use_recurring:
                identity = random.choice(available)
                identities_used_this_case.add(id(identity))
                name = random.choice(identity["variants"])
                age = identity["age"] + random.choice([-1, 0, 0, 1])
                father_name = identity["father_name"] if random.random() > 0.15 else None  # sometimes omitted, realistic
                gender = identity["gender"]
                identity["case_ids"].append(case["id"])
            else:
                gender = random.choice(["M", "M", "M", "F"])
                name = rand_name(gender)
                age = random.randint(18, 55)
                father_name = f"{random.choice(MALE_FIRST)} {name.split()[-1]}" if random.random() > 0.3 else None

            person_counter[case["id"]] = person_counter.get(case["id"], 0) + 1
            person_id = f"A{person_counter[case['id']]}"

            cur = conn.execute(
                """INSERT INTO Accused (CaseMasterID, AccusedName, AgeYear, GenderID, PersonID, FatherOrSpouseName)
                   VALUES (?,?,?,?,?,?)""",
                (case["id"], name, age, gender, person_id, father_name)
            )
            raw_accused.append({
                "ref_id": cur.lastrowid, "name": name, "age": age, "gender": gender,
                "district": case["district"], "father_name": father_name,
                "case_id": case["id"], "crime_type": case["crime_type"],
            })

    conn.commit()
    print(f"✅ Seeded {len(raw_accused)} raw per-case Accused records "
          f"(from a {len(identity_pool)}-person recurring-identity pool + one-off accused)")
    return raw_accused, identity_pool


def cluster_and_seed_identities(conn, L, raw_accused):
    """
    Runs brain/alias_resolver.cluster_identities() over every raw Accused
    row — the same function tested standalone earlier in this project —
    to resolve them into PersonIdentity records. This is not a separate
    demo function: it is the literal code path that will run against
    real KSP data too.
    """
    clusters = alias_resolver.cluster_identities(raw_accused, age_tolerance=2)

    by_ref_id = {r["ref_id"]: r for r in raw_accused}
    identity_ids = {}   # ref_id -> PersonIdentityID

    for cluster in clusters:
        members = cluster["members"]
        sample = by_ref_id[members[0]]
        case_types = [by_ref_id[m]["crime_type"] for m in members]
        prior_convictions = len(members) - 1  # every extra linked case beyond the first counts as prior history
        is_repeat = 1 if len(members) > 1 else 0

        # crude but real risk scoring, same shape as services/risk_scoring.py's inputs.
        # Severity alone shouldn't push a first-time offender into MEDIUM+ — prior
        # convictions (repeat linkage) are the dominant driver, matching how
        # services/risk_scoring.py weights the same signals.
        severity = max((SEVERITY.get(c, 3) for c in case_types), default=3)
        base = severity * 2.5
        conviction_component = min(60, prior_convictions * 10)
        repeat_bonus = 15 if is_repeat else 0
        risk_score = round(min(100, base + conviction_component + repeat_bonus), 1)
        risk_category = ("EXTREME" if risk_score >= 80 else "HIGH" if risk_score >= 55
                          else "MEDIUM" if risk_score >= 30 else "LOW")

        district_id = L["district"].get(sample["district"])
        mo = random.choice(MODUS_OPERANDI) if is_repeat else None

        cur = conn.execute(
            """INSERT INTO PersonIdentity
               (CanonicalName, PrimaryAlias, AgeYear, GenderID, DistrictID, OccupationID, EducationLevel,
                RiskScore, RiskCategory, ModusOperandi, IsRepeatOffender, PhoneNumber, FatherOrSpouseName)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cluster["canonical_name"], sample["name"] if sample["name"] != cluster["canonical_name"] else None,
             sample["age"], sample["gender"], district_id,
             L["occupation"][random.choice(OCCUPATIONS)], random.choice(EDUCATIONS),
             risk_score, risk_category, mo, is_repeat,
             f"9{random.randint(100000000,999999999)}", sample.get("father_name"))
        )
        identity_id = cur.lastrowid

        for ref_id in members:
            r = by_ref_id[ref_id]
            if len(members) == 1:
                match_confidence, match_method = 1.0, "single_record"
            else:
                matches = alias_resolver.resolve_name(r["name"], [cluster["canonical_name"]])
                match_confidence = matches[0]["confidence"] if matches else 1.0
                match_method = matches[0]["method"] if matches else "exact"
            conn.execute(
                "INSERT INTO PersonIdentityLink (PersonIdentityID, AccusedMasterID, MatchConfidence, MatchMethod) VALUES (?,?,?,?)",
                (identity_id, ref_id, match_confidence, match_method)
            )
            identity_ids[ref_id] = identity_id

    conn.commit()
    multi_member_clusters = [c for c in clusters if len(c["members"]) > 1]
    print(f"✅ Identity resolution: {len(raw_accused)} raw accused records clustered into "
          f"{len(clusters)} PersonIdentity records ({len(multi_member_clusters)} were cross-case "
          f"matches resolved via alias/phonetic/fuzzy matching — not just exact-name grouping)")
    return identity_ids


# ═══════════════════════════════════════════════════════════════════════════
# SEEDING — ARREST / CHARGESHEET, GANGS, NETWORK (Phone/Vehicle graph)
# ═══════════════════════════════════════════════════════════════════════════

def seed_arrest_and_chargesheet(conn, L, cases, raw_accused, identity_ids):
    cases_by_id = {c["id"]: c for c in cases}
    for r in raw_accused:
        if random.random() > 0.45:
            continue
        case = cases_by_id[r["case_id"]]
        conn.execute(
            """INSERT INTO ArrestSurrender
               (CaseMasterID, ArrestSurrenderTypeID, ArrestSurrenderDate, ArrestSurrenderStateId,
                ArrestSurrenderDistrictId, PoliceStationID, IOID, CourtID, AccusedMasterID, IsAccused, BailStatus)
               VALUES (?,?,?,?,?,?,?,?,?,1,?)""",
            (case["id"], 1, rand_date(2021, 2026), L["state"]["Karnataka"], case["district_id"],
             case["unit_id"], random.choice(L["employee"])["id"], L["court"][case["district"]],
             r["ref_id"], random.choice(["Bail Granted", "Bail Rejected", "None", "None"]))
        )

    charge_sheeted_cases = [c for c in cases if c["status"] == "Charge-Sheeted"]
    for case in charge_sheeted_cases:
        conn.execute("INSERT INTO ChargesheetDetails (CaseMasterID, csdate, cstype, PolicePersonID) VALUES (?,?,?,?)",
                     (case["id"], rand_date(2021, 2026), "A", random.choice(L["employee"])["id"]))

    conn.commit()
    print(f"✅ Seeded arrest/surrender records and {len(charge_sheeted_cases)} chargesheets")


GANGS = [
    {"name": "Bengaluru City Syndicate", "district": "Bengaluru Urban", "size": 8},
    {"name": "Mysuru Cyber Fraud Network", "district": "Mysuru", "size": 6},
    {"name": "Hubballi Drug Syndicate", "district": "Hubballi-Dharwad", "size": 7},
    {"name": "Dakshina Kannada Theft Ring", "district": "Mangaluru", "size": 5},
]

def assign_gangs_and_build_network(conn, identity_ids):
    """Assigns gang affiliation to a subset of higher-risk identities and
    builds PersonNetworkLink edges — the same underlying data structure
    brain/graph_engine.py's community detection was tested against."""
    rows = conn.execute("SELECT PersonIdentityID, RiskScore, DistrictID FROM PersonIdentity ORDER BY RiskScore DESC").fetchall()
    district_name_by_id = {v: k for k, v in
                            {r[0]: r[1] for r in conn.execute("SELECT DistrictName, DistrictID FROM District").fetchall()}.items()}
    # simpler: build id->name map directly
    dist_rows = conn.execute("SELECT DistrictID, DistrictName FROM District").fetchall()
    dist_name_by_id = {r[0]: r[1] for r in dist_rows}

    gang_members = {g["name"]: [] for g in GANGS}
    pool = list(rows)
    for gang in GANGS:
        candidates = [pid for pid, score, did in pool if dist_name_by_id.get(did) == gang["district"]]
        chosen = candidates[:gang["size"]]
        for pid in chosen:
            conn.execute("UPDATE PersonIdentity SET GangAffiliation=? WHERE PersonIdentityID=?", (gang["name"], pid))
            gang_members[gang["name"]].append(pid)
        pool = [(p, s, d) for p, s, d in pool if p not in chosen]

    edges = 0
    for gang_name, members in gang_members.items():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                strength = round(random.uniform(0.55, 1.0), 2)
                conn.execute(
                    "INSERT INTO PersonNetworkLink (PersonIdentityID_A, PersonIdentityID_B, RelationshipType, Strength, Notes) VALUES (?,?,?,?,?)",
                    (members[i], members[j], "Gang Member", strength, f"Both members of {gang_name}")
                )
                edges += 1

    # a handful of cross-gang / repeat-offender co-accused links, for realism
    all_ids = [r[0] for r in rows]
    for _ in min(12, len(all_ids) // 2) * [0]:
        a, b = random.sample(all_ids, 2)
        conn.execute(
            "INSERT INTO PersonNetworkLink (PersonIdentityID_A, PersonIdentityID_B, RelationshipType, Strength, Notes) VALUES (?,?,?,?,?)",
            (a, b, "Co-Accused", round(random.uniform(0.2, 0.5), 2), "Appeared in the same FIR")
        )
        edges += 1

    conn.commit()
    print(f"✅ Assigned {sum(len(m) for m in gang_members.values())} identities to {len(GANGS)} gangs, "
          f"{edges} network edges")
    return gang_members


def seed_phones_vehicles(conn, identity_ids, gang_members, cases):
    """
    Builds the Phone/Vehicle graph — including one DELIBERATE, fully
    traceable chain matching the exact scenario from the project brief:

        Person --used_phone--> Phone A --called--> Phone B --belongs_to--> Person2
                                                                  |
                                                            owns_vehicle
                                                                  v
                                                         Vehicle --seen_near--> Case

    This is real seeded data brain/graph_engine.find_hidden_paths() can
    discover — not a hardcoded response.
    """
    all_identity_ids = list(set(identity_ids.values()))
    cases_by_id = {c["id"]: c for c in cases}

    # ── Deliberate demo chain ────────────────────────────────────────────
    demo_persons = random.sample(all_identity_ids, 2)
    phone_a = conn.execute("INSERT INTO Phone (PhoneNumber) VALUES (?)", (f"9{random.randint(100000000,999999999)}",)).lastrowid
    phone_b = conn.execute("INSERT INTO Phone (PhoneNumber) VALUES (?)", (f"9{random.randint(100000000,999999999)}",)).lastrowid
    conn.execute("INSERT INTO PersonPhoneLink (PersonIdentityID, PhoneID) VALUES (?,?)", (demo_persons[0], phone_a))
    conn.execute("INSERT INTO PersonPhoneLink (PersonIdentityID, PhoneID) VALUES (?,?)", (demo_persons[1], phone_b))
    conn.execute("INSERT INTO PhoneCallLink (FromPhoneID, ToPhoneID, CallDate, DurationSeconds) VALUES (?,?,?,?)",
                 (phone_a, phone_b, rand_date(2025, 2026), random.randint(30, 600)))
    vehicle_no = f"KA{random.randint(1,60):02d}{''.join(random.choices('ABCDEFGHJKMNPQRSTUVWXYZ', k=2))}{random.randint(1000,9999)}"
    demo_vehicle = conn.execute("INSERT INTO Vehicle (RegistrationNumber, VehicleType) VALUES (?,?)",
                                 (vehicle_no, "Two-Wheeler")).lastrowid
    conn.execute("INSERT INTO PersonVehicleLink (PersonIdentityID, VehicleID) VALUES (?,?)", (demo_persons[1], demo_vehicle))
    demo_case = random.choice(list(cases_by_id.values()))
    conn.execute("INSERT INTO VehicleSighting (VehicleID, CaseMasterID) VALUES (?,?)", (demo_vehicle, demo_case["id"]))

    # ── General population of phones/vehicles for volume + realism ──────
    for pid in all_identity_ids:
        if random.random() < 0.6:
            phone_id = conn.execute("INSERT INTO Phone (PhoneNumber) VALUES (?)",
                                     (f"9{random.randint(100000000,999999999)}",)).lastrowid
            conn.execute("INSERT INTO PersonPhoneLink (PersonIdentityID, PhoneID) VALUES (?,?)", (pid, phone_id))
        if random.random() < 0.4:
            vno = f"KA{random.randint(1,60):02d}{''.join(random.choices('ABCDEFGHJKMNPQRSTUVWXYZ', k=2))}{random.randint(1000,9999)}"
            vehicle_id = conn.execute("INSERT INTO Vehicle (RegistrationNumber, VehicleType) VALUES (?,?)",
                                       (vno, random.choice(["Two-Wheeler", "Car", "Auto"]))).lastrowid
            conn.execute("INSERT INTO PersonVehicleLink (PersonIdentityID, VehicleID) VALUES (?,?)", (pid, vehicle_id))
            if random.random() < 0.5:
                conn.execute("INSERT INTO VehicleSighting (VehicleID, CaseMasterID) VALUES (?,?)",
                             (vehicle_id, random.choice(list(cases_by_id.values()))["id"]))

    # a batch of calls within each gang, so betweenness/centrality has real signal
    all_phones = [r[0] for r in conn.execute("SELECT PhoneID FROM Phone").fetchall()]
    for _ in range(60):
        a, b = random.sample(all_phones, 2)
        conn.execute("INSERT INTO PhoneCallLink (FromPhoneID, ToPhoneID, CallDate, DurationSeconds) VALUES (?,?,?,?)",
                     (a, b, rand_date(2025, 2026), random.randint(20, 800)))

    conn.commit()
    demo_person_names = conn.execute(
        "SELECT CanonicalName FROM PersonIdentity WHERE PersonIdentityID IN (?,?)",
        (demo_persons[0], demo_persons[1])
    ).fetchall()
    print(f"✅ Phone/Vehicle graph seeded. Demo chain: "
          f"{demo_person_names[0][0]} -> used_phone -> Phone -> called -> Phone -> belongs_to -> "
          f"{demo_person_names[1][0]} -> owns_vehicle -> {vehicle_no} -> seen_near -> {demo_case['crime_no']}")


# ═══════════════════════════════════════════════════════════════════════════
# SEEDING — INVESTIGATION UPDATES (stage-tagged via brain/timeline_engine.py)
# ═══════════════════════════════════════════════════════════════════════════

UPDATE_TEMPLATES = [
    "Witness statement recorded. Corroborates victim's account.",
    "Victim's medical examination conducted at the district hospital.",
    "Scene of crime inspected. Fingerprints lifted and sent to FSL.",
    "CCTV footage retrieved from a nearby camera; suspect movement captured.",
    "Seized property transferred to malkhana.",
    "FSL report received, confirming evidence collected at the scene.",
    "Additional accused identified. Look-out notice issued to neighbouring stations.",
    "Accused arrested and produced before the jurisdictional court. Remanded to custody.",
    "Charge sheet filed. Case committed to the Sessions Court.",
    "Accused granted bail by the court. Reporting conditions imposed.",
    "Case closed after investigation established the complaint was unfounded.",
    "Final report filed — case undetected despite sustained investigation efforts.",
]

def seed_investigation_updates(conn, L, cases):
    officer_names = [e["name"] for e in L["employee"]]
    total = 0
    for case in cases:
        if random.random() > 0.55:
            continue
        n_updates = random.randint(1, 4)
        for _ in range(n_updates):
            text = random.choice(UPDATE_TEMPLATES)
            stage = timeline_engine.classify_stage(text)
            conn.execute(
                "INSERT INTO InvestigationUpdate (CaseMasterID, UpdateDate, UpdateText, OfficerName, Stage) VALUES (?,?,?,?,?)",
                (case["id"], rand_date(2021, 2026), text, random.choice(officer_names), stage)
            )
            total += 1
    conn.commit()
    print(f"✅ Seeded {total} stage-tagged investigation updates (via brain/timeline_engine.classify_stage)")


# ═══════════════════════════════════════════════════════════════════════════
# SEEDING — CRIME TRENDS (feeds brain/prediction_engine.py)
# ═══════════════════════════════════════════════════════════════════════════

def seed_crime_trends(conn, L):
    records = 0
    major_districts = list(DISTRICTS.keys())[:6]
    main_crimes = list(SEVERITY.keys())   # ALL crime types — Theft (highest-weight) was
                                            # previously excluded by an arbitrary [:8] slice
    for year in range(2021, 2027):
        for month in range(1, 13):
            if year == 2026 and month > 6:
                continue
            for district in major_districts:
                for crime in main_crimes:
                    base = random.randint(5, 40)
                    if month in (10, 11) and crime in ("Theft", "Chain Snatching"):
                        base = int(base * 1.6)
                    if crime == "Cybercrime":
                        base = int(base * (1 + (year - 2021) * 0.2))
                    arrested = random.randint(0, base)
                    conn.execute(
                        "INSERT INTO CrimeTrend (Year, Month, DistrictID, CrimeSubHeadID, CaseCount, ArrestCount) VALUES (?,?,?,?,?,?)",
                        (year, month, L["district"][district], L["crime_subhead"][crime]["id"], base, arrested)
                    )
                    records += 1
    conn.commit()
    print(f"✅ Seeded {records} CrimeTrend records (2021–2026, feeds prediction_engine.py)")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n🚀 KAVACH Seed Data Generator v2 — KSP-compliant schema")
    print(f"{'─'*60}\nDatabase: {DB_PATH}\n{'─'*60}\n")

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    create_schema(conn)
    L = seed_reference_data(conn)
    cases = seed_cases(conn, L, count=500)
    raw_accused, identity_pool = seed_accused(conn, L, cases)
    identity_ids = cluster_and_seed_identities(conn, L, raw_accused)
    seed_arrest_and_chargesheet(conn, L, cases, raw_accused, identity_ids)
    gang_members = assign_gangs_and_build_network(conn, identity_ids)
    seed_phones_vehicles(conn, identity_ids, gang_members, cases)
    seed_investigation_updates(conn, L, cases)
    seed_crime_trends(conn, L)

    # Also initialise the brain's own memory tables, the auth session
    # table, the chat-document-context table (chat-with-a-PDF scratch
    # storage — see brain/document_context.py's module docstring), and
    # the prediction accuracy tracking log (see
    # brain/prediction_tracking.py) — including its one-time historical
    # backfill, so a freshly seeded database has a real, multi-year
    # settled accuracy record immediately rather than an empty table.
    from brain import (memory_engine, document_context as _document_context,
                       prediction_tracking as _prediction_tracking, feedback_engine as _feedback_engine,
                       identity_confidence as _identity_confidence, case_memory as _case_memory)
    import auth as _auth2
    from services import audit_log as _audit_log
    memory_engine.init_schema(conn)
    memory_engine.init_context_schema(conn)
    _auth2.init_schema(conn)
    _audit_log.init_schema(conn)
    _document_context.init_schema(conn)
    _prediction_tracking.init_schema(conn)
    _prediction_tracking.backfill_historical_predictions(conn)
    _feedback_engine.init_schema(conn)
    _identity_confidence.init_schema(conn)
    _identity_confidence.backfill_all_identities(conn)
    _case_memory.init_schema(conn)

    print(f"\n{'─'*60}\n📊 Final table counts:")
    tables = ["State","District","Unit","Employee","CaseMaster","ComplainantDetails","Victim",
              "Accused","PersonIdentity","PersonIdentityLink","ArrestSurrender","ChargesheetDetails",
              "Phone","Vehicle","PersonNetworkLink","InvestigationUpdate","CrimeTrend","Users"]
    for t in tables:
        c = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:22s}: {c:>5}")

    print(f"\n✅ KAVACH database ready at: {DB_PATH}")
    print("\n🔐 Demo login credentials (REAL bcrypt-hashed passwords, not a placeholder):")
    print("   investigator1 / Kavach@2026")
    print("   analyst1      / Kavach@2026")
    print("   supervisor1   / Kavach@2026")
    print("   admin         / Kavach@2026")
    print("   (Change these before any real deployment — see README.)")
    print("\nRun: uvicorn main:app --reload\n")
    conn.close()


if __name__ == "__main__":
    main()
