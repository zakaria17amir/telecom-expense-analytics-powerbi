"""Synthetic data generator for the Telecom Expense & Service Management Analytics report.

    python scripts/generate_data.py          # writes ./data/*.csv (deterministic, seed 42)

Simulates ~500 corporate mobile lines for the fictional company "Contoso" across five carriers
(Jan 2024 - Aug 2026): carrier bills, device inventory, service-desk tickets, approvals and the
savings initiatives tracked by the mobility team. Column names and order are read from the
semantic model's TMDL files, so the CSVs always match what Power Query expects.

Built-in realism: summer / December roaming peaks, device installment plans, a 3% FY26 price
increase, suspended and zero-usage lines, VVIP travellers, users with 3+ devices, and a
decreasing trend in data-quality discrepancies.
"""
import calendar
import csv
import random
import uuid
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MODEL = ROOT / "Telecom Expense and Service Management Analytics.SemanticModel" / "definition"
START, END = date(2024, 1, 1), date(2026, 8, 31)  # billing history; Aug-26 is the "latest month"
rnd = random.Random(42)

# ---------------------------------------------------------------- helpers

def months(start=START, end=END):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def day(y, m, d):
    return date(y, m, min(d, calendar.monthrange(y, m)[1]))


def rdate(a, b):
    return a + timedelta(days=rnd.randint(0, (b - a).days))


def add_bdays(d, n):
    while n > 0:
        d += timedelta(days=1)
        n -= d.weekday() < 5
    return d


def pick(weighted):  # {value: weight}
    return rnd.choices(list(weighted), list(weighted.values()))[0]


def num(n):
    return str(rnd.randint(10 ** (n - 1), 10 ** n - 1))


def yn(p):
    return "Yes" if rnd.random() < p else "No"


# ---------------------------------------------------------------- reference data

FIRST = ("James Mary Robert Patricia John Jennifer Michael Linda David Elizabeth William Barbara Richard Susan "
         "Joseph Jessica Thomas Sarah Charles Karen Daniel Nancy Matthew Lisa Anthony Betty Mark Sandra Steven "
         "Ashley Paul Emily Andrew Michelle Joshua Amanda Kevin Melissa Brian Stephanie Priya Wei Carlos Sofia "
         "Ahmed Fatima Hiroshi Yuki Olga Mateo Chloe Liam Noah Ava Mia Ethan Zoe Omar Leila Raj Ana").split()
LAST = ("Smith Johnson Williams Brown Jones Garcia Miller Davis Rodriguez Martinez Hernandez Lopez Gonzalez "
        "Wilson Anderson Thomas Taylor Moore Jackson Martin Lee Perez Thompson White Harris Sanchez Clark Ramirez "
        "Lewis Robinson Walker Young Allen King Wright Scott Torres Nguyen Hill Flores Green Adams Nelson Baker "
        "Hall Rivera Campbell Mitchell Carter Roberts Patel Chen Kim Singh Tremblay Roy Gagnon Cohen Novak").split()
DEPTS = {"Finance": (41100, 8), "Supply Chain": (41200, 16), "Marketing": (41300, 14), "Sales": (41400, 22),
         "Information Technology": (41500, 10), "Human Resources": (41600, 5), "Research & Development": (41700, 9),
         "Operations": (41800, 12), "Legal": (41900, 3), "Executive Office": (42000, 2)}
ANALYSTS = ["Dana Whitfield", "Marco Bellini", "Aisha Karim", "Tom Okafor", "Grace Lindqvist", "Victor Hale"]

# name: (weight, bill-cycle day, label, area codes)
CARRIERS = {
    "Verizon United States": (42, 22, "VZW Corporate", [212, 646, 917, 201, 973, 631]),
    "AT&T United States": (30, 15, "ATT Corporate", [310, 415, 312, 404, 305, 214]),
    "T-Mobile United States": (10, 8, "TMO Corporate", [206, 503, 702, 480]),
    "Bell Canada": (10, 12, "Bell Enterprise", [416, 647, 905]),
    "Rogers Canada": (8, 18, "Rogers Enterprise", [514, 604, 437]),
}
ACCOUNTS = {c: f"{num(9)}-{rnd.randint(1, 9):05d}" for c in CARRIERS}

# model: (category, platform, retail, weight, colors)
DEVICES = {
    "Apple iPhone 16": ("Smart Phone", "iOS", 829, 14, ["Black", "White", "Teal"]),
    "Apple iPhone 15": ("Smart Phone", "iOS", 729, 22, ["Black", "Blue", "Pink"]),
    "Apple iPhone 14": ("Smart Phone", "iOS", 629, 16, ["Midnight", "Starlight", "Blue"]),
    "Apple iPhone 13": ("Smart Phone", "iOS", 529, 9, ["Midnight", "Starlight"]),
    "Apple iPhone SE": ("Smart Phone", "iOS", 429, 5, ["Black", "White"]),
    "Samsung Galaxy S24": ("Smart Phone", "Android", 799, 6, ["Onyx Black", "Marble Grey"]),
    "Samsung Galaxy S23": ("Smart Phone", "Android", 699, 5, ["Phantom Black", "Cream"]),
    "Google Pixel 8": ("Smart Phone", "Android", 699, 3, ["Obsidian", "Hazel"]),
    "Apple iPad Air": ("Tablet", "iOS", 599, 5, ["Space Grey", "Blue"]),
    "Apple iPad 10th Gen": ("Tablet", "iOS", 449, 4, ["Silver", "Blue"]),
    "Samsung Galaxy Tab S9": ("Tablet", "Android", 799, 2, ["Graphite"]),
    "Inseego MiFi X PRO": ("Hotspot", "Other", 299, 4, ["Black"]),
    "Netgear Nighthawk M6": ("Hotspot", "Other", 499, 3, ["Black"]),
    "Kyocera DuraXV Extreme": ("Basic Phone", "Other", 249, 2, ["Black"]),
}
PLANS = {  # category: [(plan, data plan, MRC)]
    "Smart Phone": [("Business Unlimited", "Unlimited Data", 45.0), ("Business Unlimited Plus", "Unlimited Premium Data", 55.0),
                    ("Flexible Business Pool", "Pooled Data 10GB", 35.0)],
    "Tablet": [("Tablet Data 10GB", "Tablet Data 10GB", 20.0), ("Tablet Unlimited", "Unlimited Tablet Data", 30.0)],
    "Hotspot": [("Mobile Hotspot 50GB", "Hotspot Data 50GB", 40.0)],
    "Basic Phone": [("Voice & Text Basic", "No Data", 25.0)],
}
ROAM_SEASON = {6: 1.8, 7: 2.2, 8: 1.9, 12: 1.6, 3: 1.3, 4: 1.2}

# ---------------------------------------------------------------- core entities

def make_people(n=620):
    names, people = set(), []
    while len(people) < n:
        f, l = rnd.choice(FIRST), rnd.choice(LAST)
        if (f, l) in names:
            continue
        names.add((f, l))
        dept = pick({d: w for d, (_, w) in DEPTS.items()})
        people.append({"name": f"{f} {l}", "email": f"{f.lower()}.{l.lower()}@contoso.com", "dept": dept,
                       "cc": DEPTS[dept][0] + rnd.randint(0, 9), "active": yn(0.94)})
    managers = {}
    for p in people:
        managers.setdefault(p["dept"], []).append(p)
    for p in people:
        boss = rnd.choice(managers[p["dept"]][:6])
        p["sup"] = boss if boss is not p else managers[p["dept"]][-1]
    return people


def imei():
    return int("35" + num(13))


used_numbers = set()


def phone(carrier):
    while True:
        n = f"{rnd.choice(CARRIERS[carrier][3])}{rnd.randint(200, 999)}{rnd.randint(0, 9999):04d}"
        if n not in used_numbers:
            used_numbers.add(n)
            return n


def make_lines(people, n=580):
    owners = [p for p in people if p["dept"] == "Executive Office"] + rnd.sample(people, 440)
    heavy = rnd.sample(owners, 26)  # people carrying 3-4 devices -> "Multiple Devices"
    owners += [p for h in heavy for p in [h] * rnd.randint(2, 3)]
    lines = []
    for i, owner in enumerate(owners[:n] if len(owners) > n else owners):
        carrier = pick({c: v[0] for c, v in CARRIERS.items()})
        model = pick({m: v[3] for m, v in DEVICES.items()})
        cat = DEVICES[model][0]
        plan, data_plan, mrc = rnd.choice(PLANS[cat])
        activated = rdate(date(2021, 6, 1), START) if rnd.random() < 0.8 else rdate(START, END - timedelta(days=40))
        status = pick({"Active": 86, "Suspended": 7, "Cancelled": 7})
        status_date = rdate(max(activated, date(2024, 6, 1)), END) if status != "Active" else None
        cstart = None if rnd.random() < 0.07 else rdate(max(activated, date(2022, 7, 1)), END)
        lines.append({
            "id": 100001 + i, "number": phone(carrier), "carrier": carrier, "owner": owner, "model": model,
            "cat": cat, "plan": plan, "data_plan": data_plan, "mrc": mrc, "activated": activated,
            "status": status, "status_date": status_date, "cstart": cstart,
            "cend": cstart.replace(year=cstart.year + 2) if cstart and not (cstart.month == 2 and cstart.day == 29) else cstart,
            "imei": imei(), "prev_imei": imei(), "serial": int(num(10)), "esim": rnd.random() < 0.35,
            "traveler": owner["dept"] in ("Executive Office", "Sales", "Supply Chain") and rnd.random() < 0.45
                        or rnd.random() < 0.06,
            "zero_use": rnd.random() < 0.05, "installment": rnd.random() < 0.35,
            "feature": rnd.choice([0.0, 0.0, 5.0, 10.0]),
        })
    return lines


# ---------------------------------------------------------------- tables

def billings(lines):
    rows = []
    for y, m in months():
        season = ROAM_SEASON.get(m, 1.0)
        for ln in lines:
            cyc = day(y, m, CARRIERS[ln["carrier"]][1])
            if ln["activated"] > cyc or (ln["status"] == "Cancelled" and ln["status_date"] < cyc.replace(day=1)):
                continue
            suspended = ln["status"] == "Suspended" and ln["status_date"] <= cyc
            mrc = round(ln["mrc"] * (1.03 if cyc >= date(2025, 7, 1) else 1.0) * (0.25 if suspended else 1), 2)
            c = {k: 0.0 for k in ("air", "ld", "vroam", "droam", "dusage", "msg", "mroam", "da", "equip", "misc", "adj", "cred")}
            if not suspended and not ln["zero_use"]:
                if ln["traveler"] and rnd.random() < 0.16 * season:
                    c["droam"] = 10.0 * rnd.randint(2, 14) if rnd.random() < 0.8 else round(rnd.uniform(40, 420), 2)
                    c["vroam"] = round(rnd.uniform(0, 70), 2)
                    c["mroam"] = round(rnd.uniform(0, 12), 2)
                if rnd.random() < 0.25:
                    c["ld"] = round(rnd.uniform(0.5, 28), 2)
                c["air"] = round(rnd.uniform(5, 30), 2) if rnd.random() < 0.01 else 0.0
                c["dusage"] = 15.0 if rnd.random() < 0.02 else 0.0
                c["msg"] = round(rnd.uniform(2, 10), 2) if rnd.random() < 0.01 else 0.0
                c["da"] = 1.99 if rnd.random() < 0.01 else 0.0
            if ln["installment"] and ln["cstart"] and 0 <= (cyc - ln["cstart"]).days < 730:
                c["equip"] = round(DEVICES[ln["model"]][2] / 24, 2)
            c["misc"] = round(rnd.uniform(5, 25), 2) if rnd.random() < 0.03 else 0.0
            c["adj"] = round(rnd.uniform(-20, 20), 2) if rnd.random() < 0.02 else 0.0
            c["cred"] = -round(rnd.uniform(5, 50), 2) if rnd.random() < 0.04 else 0.0
            data_mrc = 10.0 if ln["cat"] == "Hotspot" else 0.0
            fees = round(rnd.uniform(1.5, 3.5), 2)
            taxes = round(0.08 * (mrc + ln["feature"] + data_mrc), 2)
            sur = round(0.04 * mrc, 2)
            total = round(mrc + data_mrc + ln["feature"] + sum(c.values()) + fees + taxes + sur, 2)
            idle = suspended or ln["zero_use"] or ln["cat"] in ("Tablet", "Hotspot")
            minutes = 0 if idle else max(0, int(rnd.gauss(430, 220)))
            owner = ln["owner"]
            rows.append({
                "Carrier": ln["carrier"], "Carrier Account": ACCOUNTS[ln["carrier"]], "Bill Cycle End Date": cyc,
                "International Number": ln["number"], "Carrier Label": CARRIERS[ln["carrier"]][2],
                "Person": owner["name"], "Cost Center": str(owner["cc"]), "Group": owner["dept"],
                "Ref Device -> Platform": DEVICES[ln["model"]][1], "Ref Device": ln["model"], "Plan": ln["plan"],
                "Data Plan Name": ln["data_plan"], "Text Plan Name": "" if ln["cat"] in ("Tablet", "Hotspot") else "Unlimited Messaging",
                "Line Bill -> Total Rebilled Charges": total, "Line Bill -> Rebilled Primary Plan MRC": mrc,
                "Line Bill -> Carrier Data MRC": data_mrc, "Line Bill -> Carrier Text MRC": 0.0,
                "Line Bill -> Carrier Feature MRC": ln["feature"], "Line Bill -> Additional Airtime Charges": c["air"],
                "Line Bill -> Long Distance Charges": c["ld"], "Line Bill -> Voice Roaming Charges": c["vroam"],
                "Line Bill -> Data Roaming Charges": c["droam"], "Line Bill -> Data Usage Charges": c["dusage"],
                "Line Bill -> Messaging Charges": c["msg"], "Line Bill -> Roaming Messaging Charges": c["mroam"],
                "Line Bill -> Directory Assistance Charges": c["da"], "Line Bill -> Equipment Charges": c["equip"],
                "Line Bill -> Miscellaneous Charges": c["misc"], "Line Bill -> Adjustment": c["adj"],
                "Line Bill -> Credits": c["cred"], "Line Bill -> Fees": fees, "Line Bill -> Taxes": taxes,
                "Line Bill -> Surcharges": sur, "Line Bill -> Included Minute Plan Allowance": 0.0,
                "Line Bill -> Total Minutes Used": minutes, "Line Bill -> Plan Minutes Used": int(minutes * 0.88),
                "Line Bill -> Nights And Weekends Minutes Used": int(minutes * 0.07),
                "Line Bill -> Mobile To Mobile Minutes Used": int(minutes * 0.03), "Line Bill -> PTT Minutes Used": 0,
                "Line Bill -> Long Distance Minutes Used": int(minutes * 0.02) if c["ld"] else 0,
                "Line Bill -> Roaming Minutes Used": int(c["vroam"] * 4), "Line Bill -> Other Minutes Used": 0,
                "Line Bill -> Directory Assistance Calls": 1 if c["da"] else 0,
                "Line Bill -> Messages Used": 0 if idle else max(0, int(rnd.gauss(600, 300))),
                "Line Bill -> Roaming Messages Used": int(c["mroam"] * 20),
                "Line Bill -> Domestic Data KBs Used": 0 if suspended or ln["zero_use"] else int(abs(rnd.gauss(7, 5)) * 1048576),
                "Line Bill -> Roaming Data KBs Used": int(c["droam"] * 20480),
                "Product Category": ln["cat"], "Device Manufacturer": ln["model"].split(" ")[0],
            })
    return rows


def all_lines(lines):
    rows = []
    for ln in lines:
        o = ln["owner"]
        rows.append({
            "International Number": ln["number"], "Formula": ln["id"], "Line Status": ln["status"],
            "Do Not Change": rnd.random() < 0.03, "Owner -> Do Not Change": o["dept"] == "Executive Office",
            "Carrier": ln["carrier"], "Carrier Label": CARRIERS[ln["carrier"]][2], "Owner": o["name"],
            "Owner -> Active?": o["active"], "Owner -> Email": o["email"], "Employee -> Cost Center": o["cc"],
            "Cost Center": str(o["cc"]), "Owner -> Supervisor": o["sup"]["name"], "Owner -> Supervisor Email": o["sup"]["email"],
            "Ref Device": ln["model"], "Plan": ln["plan"], "Plan -> Plan Name": ln["plan"], "Is ESIM": ln["esim"],
            "Contract Start Date": ln["cstart"], "Contract Ends Date": ln["cend"],
            "Suspended At": ln["status_date"].isoformat() if ln["status"] == "Suspended" else "",
            "Upgrade Eligible Date": ln["cend"], "Line Bill -> Total Recurring Charges": ln["mrc"] + ln["feature"],
            "Line Bill -> Total Charges": round(ln["mrc"] * 1.15 + ln["feature"], 2),
            "Zerouserecommendationrejected": int(ln["zero_use"] and rnd.random() < 0.3),
            "IMEI": ln["imei"], "Device -> IMEI": ln["imei"], "Previous Device -> IMEI2": ln["prev_imei"],
            "Serial": ln["serial"], "Device -> Serial Number": f"F{ln['serial']}", "Owner -> Group": o["dept"],
        })
    return rows


def out_of_contract(lines):
    return [{"International Number": l["number"], "Line Status": l["status"], "Carrier": l["carrier"],
             "Contract Start Date": l["cstart"], "Contract Ends": l["cend"]}
            for l in lines if l["status"] != "Cancelled"]


def tangoe_devices(lines):
    rows = [{"Model": l["model"], "Person": l["owner"]["name"], "Group": l["owner"]["dept"],
             "Cost Center": str(l["owner"]["cc"]), "Device Category": l["cat"], "Identifier": str(l["imei"]),
             "Carrier": l["carrier"], "Line -> Product Category": l["cat"]}
            for l in lines if l["status"] != "Cancelled"]
    for _ in range(30):  # spare / unassigned devices
        model = pick({m: v[3] for m, v in DEVICES.items()})
        rows.append({"Model": model, "Person": "", "Group": "", "Cost Center": "", "Device Category": DEVICES[model][0],
                     "Identifier": str(imei()), "Carrier": pick({c: v[0] for c, v in CARRIERS.items()}),
                     "Line -> Product Category": DEVICES[model][0]})
    return rows


def vvip_and_exceptions(lines):
    travelers = [l for l in lines if l["status"] == "Active" and l["cat"] == "Smart Phone"]
    execs = [l for l in travelers if l["owner"]["dept"] == "Executive Office"]
    others = [l for l in travelers if l["traveler"] and l not in execs]
    vvip = execs[:12] or others[:12]
    for l in vvip:
        l["traveler"] = True
    exc = rnd.sample([l for l in others if l not in vvip], 30)
    comments = ["Frequent international travel", "Global role - regional HQ visits", "Approved by VP - trade shows",
                "Supplier site visits (APAC)", "Temporary assignment in EMEA", "Canada/US cross-border commuter"]
    return ([{"Name": l["owner"]["name"], "Device number": int(l["number"]), "Carrier": l["carrier"]} for l in vvip],
            [{"Name": l["owner"]["name"], "Device Number": int(l["number"]), "Carrier": l["carrier"],
              "Comment": rnd.choice(comments)} for l in exc])


def granite():
    stores = [f"Contoso Store #{n:03d}" for n in rnd.sample(range(1, 400), 150)]
    overall, total = [], len(stores)
    for i, store in enumerate(stores):
        usage = round(abs(rnd.gauss(1.6, 1.1)), 3)
        model = rnd.choice(["Apple iPad 10th Gen", "Apple iPad Air"])
        overall.append({
            "PlanId": 7701 + i % 3, "ConnectionID": 5400000 + i, "TotalRecords": total, "AccountNumber": 880100 + i % 3,
            "AccountName": ["Retail East", "Retail West", "Distribution"][i % 3], "ParentAccountNumber": 880000,
            "ParentAccountName": "Contoso Retail", "Iccid": int("8901" + num(15)), "Msisdn": int(phone("AT&T United States")),
            "Imei": imei(), "PlanName": "Granite Tablet 5GB Pool", "PlanType": "Pooled", "PlanLimit": "5 GB",
            "PlanUsage": usage, "PlanUsagePercentage": round(usage / 5, 4), "SimLimit": "5 GB", "SimUsage": usage,
            "SimUsagePercentage": round(usage / 5, 4), "Username": store, "Status": "Active",
            "PlanAlias": "POS Tablets", "SimAlias": store, "CycleDate": "07/01/2026 - 07/31/2026", "Cycle": date(2026, 7, 31),
            "Manufacturer": "Apple", "Model": model, "IPType": "Dynamic",
            "IPAddress": f"10.{rnd.randint(0, 255)}.{rnd.randint(0, 255)}.{rnd.randint(1, 254)}",
            "SubnetMask": "255.255.255.0", "DefaultGateway": "10.0.0.1", "CycleDay": "1", "Location": store,
            "ModelNumber": "A2696" if "10th" in model else "A2589", "BundleType": "Data Only", "EquipmentId": 990000 + i,
            "EqiupmentProduct": model, "CustomField1": "POS", "CustomField2": "", "GeneralLedger": "6420-100",
            "BranchNumber": store[-3:], "Employer": "Contoso", "Length": 10,
        })
    rock, inv = [], 4410000
    for y, m in months():
        for k, (loc, base) in enumerate([("Retail East", 3900), ("Retail West", 3300), ("Distribution", 1700)]):
            new = round(base * (1 + 0.004 * (y * 12 + m - 2024 * 12)) * rnd.uniform(0.94, 1.08), 2)
            inv += 1
            latest = (y, m) == (END.year, END.month)
            rock.append({"Invoice Number": inv, "Invoice Date": day(y, m, 5), "Parent Account": 880000,
                         "Account #": 880100 + k, "Location Name": loc, "Status": "Open" if latest else "Paid",
                         "Current Due": new if latest else 0.0, "Previous": round(new * rnd.uniform(0.95, 1.05), 2),
                         "New Charges": new, "Payments": 0.0 if latest else -new, "Adjustments": 0.0,
                         "Applied": 0.0 if latest else new, "Carrier": "Granite"})
    return overall, rock


def savings_tables(lines):
    active_inactive, zero_use = [], []
    for y, m in months(date(2024, 7, 1)):
        for c in CARRIERS:
            if rnd.random() < 0.6:
                q = rnd.randint(1, 9)
                mrc = round(q * rnd.uniform(40, 55), 2)
                active_inactive.append({"Date": day(y, m, 28), "Carrier": c, "Qty": q,
                                        "Monthly Recurring Charges": mrc, "Annual Saving": round(mrc * 12, 2)})
        found = rnd.randint(18, 42)
        q = round(found * rnd.uniform(0.45, 0.85))
        mrc = round(q * rnd.uniform(38, 48), 2)
        zero_use.append({"Date": day(y, m, 28), "Qty": q, "Monthly Recurring Charges": mrc,
                         "Annual Saving": round(mrc * 12, 2), "Lines Found": found})
    vz = [l for l in lines if l["carrier"] == "Verizon United States" and l["cat"] == "Smart Phone"]
    newer = ["Apple iPhone 16", "Apple iPhone 15", "Samsung Galaxy S24"]
    verizon = []
    for l in rnd.sample(vz, 72):
        cb = rdate(date(2024, 8, 1), date(2026, 9, 30))
        dev = rnd.choice(newer)
        retail, paid = DEVICES[dev][2] + 0.99, rnd.choice([0.99, 0.99, 199.99])
        verizon.append({
            "Wireless number": l["number"], "Wireless number status": "Active", "Owner": l["owner"]["name"],
            "Owner -> Email": l["owner"]["email"], "Owner -> Do Not Change": "No", "Current device ID": str(l["prev_imei"]),
            "Current device": l["model"], "Ordered device ID": str(l["imei"]), "Ordered device": dev,
            "Chargeback date": cb, "Number of Days Left": str(max(0, (cb - END).days)),
            "Full retail price": f"{retail:.2f}", "Purchase price": f"{paid:.2f}", "Chargeback amount": round(retail - paid, 2),
            "Email sent": "Yes", "Reminder": yn(0.7), "2nd Reminder": yn(0.35), "Contacted via Teams": yn(0.25),
            "Activation confirmed": yn(0.85),
        })
    return active_inactive, zero_use, verizon


def depot(people):
    phones = [m for m, v in DEVICES.items() if v[0] in ("Smart Phone", "Tablet")]
    def device(model):
        return {"Model": model, "Mfr": model.split(" ")[0], "Color": rnd.choice(DEVICES[model][4]),
                "Memory (Gb)": rnd.choice(["64", "128", "128", "256"]), "Carrier Lock": "Unlocked",
                "Carrier": pick({c: v[0] for c, v in CARRIERS.items()}), "iOS Lock": "No", "MDM": "Intune",
                "IMEI": str(imei()), "Serial Number": "F" + num(10), "EID": num(18)}
    inventory = []
    for _ in range(88):
        d = device(rnd.choice(phones))
        d.update({"Carrier Lock Status": "Unlocked", "ETF": "0", "Contract End": "", "Tangoe Administered? ": yn(0.8),
                  "Deployed": "No"})
        inventory.append(d)
    reissued = []
    for _ in range(134):
        p, d = rnd.choice(people), device(rnd.choice(phones))
        given = None if rnd.random() < 0.05 else rdate(date(2024, 9, 1), END)
        d.update({"New user": p["name"], "Email address": p["email"], "Date of giving out": given,
                  "Tracking info": "1Z" + num(16), "Reissued": "Yes", "Comment": rnd.choice(["", "", "Replacement for damaged device", "New hire"]),
                  "Comment 2": "", "ETF": 0.0, "Contract End": rdate(date(2025, 1, 1), date(2027, 12, 31)),
                  "IMEI2": num(15), "ICCID": "8901" + num(15), "UIDID": uuid.UUID(int=rnd.getrandbits(128)).hex[:24].upper(),
                  "SrcPartNum": "M" + num(4) + "LL/A", "Availability": "Deployed", "Carrier_1": d["Carrier"]})
        reissued.append(d)
    returned = []
    for i in range(162):
        model = rnd.choice(["Apple iPhone 11", "Apple iPhone 12", "Apple iPhone 13", "Apple iPhone 14",
                            "Samsung Galaxy S21", "Samsung Galaxy S22", "Apple iPad 9th Gen"])
        cond = pick({"Excellent": 15, "Good": 35, "Fair": 25, "Poor": 15, "Broken": 10})
        powers, lock = yn(0.92 if cond != "Broken" else 0.3), pick({"None": 80, "iCloud Lock": 10, "Carrier Lock": 6, "MDM Lock": 4})
        base = {"11": 90, "12": 150, "13": 230, "14": 320, "S21": 110, "S22": 170, "9th": 120}[model.split(" ")[-1] if "iPad" not in model else "9th"]
        factor = {"Excellent": 1.0, "Good": 0.8, "Fair": 0.55, "Poor": 0.25, "Broken": 0}[cond]
        value = 0.0 if powers == "No" or lock != "None" else round(base * factor * rnd.uniform(0.9, 1.1), 2)
        returned.append({"Device": model, "ESN/IMEI": str(imei()), "Serial#": "F" + num(10), "Value": value,
                         "Condition": cond, "Powers Up": powers, "Damaged Screen": yn(0.6 if cond in ("Poor", "Broken") else 0.05),
                         "Lock Type": lock, "Data Cleared": yn(0.97), "Order": 70001 + i // 6, "Device ID": 910000 + i,
                         "Date": rdate(date(2024, 11, 1), END)})
    return inventory, reissued, returned


def activities(lines):
    types = {"Order New Device and Service": 18, "Upgrade Device": 22, "Travel Request": 18, "Suspend Service": 8,
             "Disconnect Service": 10, "Change Plan / Feature": 12, "Transfer of Liability": 5, "Lost / Stolen Device": 7}
    rows = []
    for i in range(1550):
        created = rdate(START, date(2026, 9, 20))
        t = pick({k: w * (ROAM_SEASON.get(created.month, 1.0) if k == "Travel Request" else 1) for k, w in types.items()})
        recent = (date(2026, 9, 25) - created).days < 20
        state = pick({"Complete": 60, "In Progress": 35, "Cancelled": 5} if recent else {"Complete": 90, "In Progress": 2, "Cancelled": 8})
        l = rnd.choice(lines)
        dep = created + timedelta(days=rnd.randint(3, 30)) if t == "Travel Request" else None
        rows.append({"Activity Type": t, "Created": created, "ID": 2600000 + i, "Person Activity For": l["owner"]["name"],
                     "Line": l["number"], "Carrier": l["carrier"], "Departure Date": dep,
                     "Return Date": dep + timedelta(days=rnd.randint(3, 21)) if dep else None,
                     "Completed At": add_bdays(created, rnd.randint(0, 6)) if state == "Complete" else None,
                     "Activity State": state})
    return rows


def tickets(people):
    kinds = {"New Device": ("New mobile device request", 22), "Device Upgrade": ("Mobile device upgrade", 20),
             "International Travel": ("International roaming plan for upcoming travel", 18),
             "Lost/Stolen": ("Lost or stolen device - suspend line", 7), "Troubleshooting": ("Mobile device not working", 16),
             "Number Port": ("Port personal number to corporate account", 5),
             "Line Cancellation": ("Cancel mobile line - employee departure", 9), "N/A": ("General mobility inquiry", 3)}
    user = {a: a.split()[0][0].lower() + a.split()[1].lower() for a in ANALYSTS}
    rows = []
    for i in range(1180):
        created = rdate(START, date(2026, 9, 20))
        kind = pick({k: v[1] for k, v in kinds.items()})
        age = (date(2026, 9, 25) - created).days
        state = pick({"Closed Complete": 88, "Closed Incomplete": 6, "Work in Progress": 4, "Open": 2} if age > 30
                     else {"Closed Complete": 45, "Work in Progress": 35, "Open": 20})
        closed = add_bdays(created, max(0, int(rnd.gauss(3, 2)))) if state.startswith("Closed") else None
        a, p = rnd.choice(ANALYSTS), rnd.choice(people)
        country = "Canada" if rnd.random() < 0.15 else "United States"
        rows.append({"number": f"RITM{1045000 + i:07d}", "priority": pick({"4 - Low": 55, "3 - Moderate": 35, "2 - High": 10}),
                     "state": state, "region": "North America", "country": country, "assigned_to": a,
                     "short_description": kinds[kind][0], "sys_class_name": "sc_req_item", "assigned_to.active": "true",
                     "assigned_to.user_name": user[a], "assignment_group": "Mobility Services NA",
                     "work_notes": "Request fulfilled via Tangoe" if closed else "Awaiting carrier confirmation",
                     "sys_updated_on": closed or created, "sys_updated_by": user[a], "sys_created_on": created,
                     "u_request_type1": kind, "sys_created_by": p["email"].split("@")[0], "closed_at": closed,
                     "description": f"{kinds[kind][0]} for {p['name']} ({country})", "u_task_for": p["name"],
                     "closed_by": a if closed else ""})
    return rows


def data_quality(lines, people):
    disc = []
    types = {"Missing in Tangoe": 9, "Missing on Carrier Bill": 6, "Plan Mismatch": 12, "Cost Center Mismatch": 8, "Owner Mismatch": 5}
    for idx, (y, m) in enumerate(months(date(2025, 1, 1))):
        decay = 1 - idx * 0.025
        for c, (w, *_) in CARRIERS.items():
            for t, base in types.items():
                disc.append({"Date": day(y, m, 1), "Carrier": c, "Type": t,
                             "Count": max(0, round(rnd.gauss(base * w / 30 * decay, 2)))})
    counts = Counter(l["owner"]["email"] for l in lines if l["status"] != "Cancelled")
    multi = [{"Owner -> Email": e, "Count": n} for e, n in counts.items() if n > 2]
    unassigned = []
    for _ in range(146):
        c = pick({k: v[0] for k, v in CARRIERS.items()})
        model = pick({m: v[3] for m, v in DEVICES.items()})
        unassigned.append({"International Number": int(phone(c)), "Carrier": c, "Account Number": int(ACCOUNTS[c].split("-")[0]),
                           "Line Status": pick({"Active": 70, "Suspended": 30}), "Findings Owner": rnd.choice(ANALYSTS),
                           "IMEI": imei(), "Device": model, "Cost Center": rnd.choice(people)["cc"],
                           "Action": pick({"Assigned": 38, "Cancelled": 27, "Suspended": 17, "Under Review": 12, "Pending Owner Confirmation": 6}),
                           "Address": f"{rnd.randint(10, 9999)} {rnd.choice(['Main St', 'Market St', 'King St W', 'Oak Ave', 'Lakeshore Blvd'])}",
                           "Line Bill -> Total Charges": f"{rnd.uniform(20, 75):.2f}"})
    return disc, multi, unassigned


def approvals(people):
    def batch(n, kind, start_id):
        rows = []
        for i in range(n):
            deadline = rdate(date(2024, 6, 1), date(2026, 9, 30))
            pending_p = 0.6 if deadline > date(2026, 9, 10) else 0.03
            decision = "" if rnd.random() < pending_p else pick({"Approve": 84, "Reject": 16})
            rows.append({"Activity Number": start_id + i, "Type": kind, " Name": rnd.choice(people)["name"],
                         "Carrier": pick({c: v[0] for c, v in CARRIERS.items()}), "Deadline": deadline, "Decision": decision})
        return rows
    orders, upgrades, old = batch(160, "New", 3100000), batch(220, "Upgrade", 3200000), batch(60, "New", 3000000)
    combined = [dict(r, Decision=r["Decision"] or "Pending") for r in orders + upgrades + old]
    return orders, upgrades, combined


# ---------------------------------------------------------------- output

def parse_columns(tmdl_text):
    """[(sourceColumn, dataType)] for the imported (non-calculated) columns of a TMDL table."""
    cols, dtype = [], None
    for line in tmdl_text.splitlines():
        if line.startswith("\tcolumn "):
            dtype = None
        elif line.startswith("\t\tdataType: "):
            dtype = line.split(": ", 1)[1].strip()
        elif line.startswith("\t\tsourceColumn: "):
            src = line.split(": ", 1)[1].strip()
            cols.append((src[1:-1] if src.startswith('"') else src, dtype))
    return cols


M_TYPES = {"string": "type text", "int64": "Int64.Type", "double": "type number", "dateTime": "type date", "boolean": "type logical"}




def write_csv(table, rows):
    cols = [c for c, _ in parse_columns((MODEL / "tables" / f"{table}.tmdl").read_text(encoding="utf-8"))]
    extra = set().union(*(r.keys() for r in rows)) - set(cols)
    assert not extra, f"{table}: columns not in model: {extra}"
    def fmt(v):
        if v is None:
            return ""
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, date):
            return v.isoformat()
        if isinstance(v, float):
            return f"{v:.4f}".rstrip("0").rstrip(".")
        return str(v)
    with open(DATA / f"{table}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows([fmt(r.get(c)) for c in cols] for r in rows)
    print(f"  {table:42} {len(rows):>6} rows")


def main():
    DATA.mkdir(exist_ok=True)
    people = make_people()
    lines = make_lines(people)
    vvip, exceptions = vvip_and_exceptions(lines)  # marks VVIPs as travellers before billing is generated
    g_overall, g_rock = granite()
    active_inactive, zero_use, verizon = savings_tables(lines)
    inventory, reissued, returned = depot(people)
    disc, multi, unassigned = data_quality(lines, people)
    orders, upgrades, combined = approvals(people)

    print(f"Writing CSVs to {DATA}")
    for table, rows in {
        "Monthly Billings All": billings(lines), "All Lines Report": all_lines(lines),
        "Out Of Contract Devices": out_of_contract(lines), "Tangoe Devices": tangoe_devices(lines),
        "VVIP List": vvip, "Exception List": exceptions, "Granite Overall": g_overall, "Granite Rock Report": g_rock,
        "Active Inactive Users": active_inactive, "Zero Use Report": zero_use, "Verizon Activation": verizon,
        "Device Depot Inventory": inventory, "Reissued Devices": reissued, "Returned Devices": returned,
        "Tangoe Activities": activities(lines), "ServiceNow Tickets": tickets(people),
        "Carrier Discrepancies": disc, "Multiple Devices": multi, "Unassigned Lines": unassigned,
        "Device Orders": orders, "Device Upgrade": upgrades, "Upgrades and Order Approvals": combined,
    }.items():
        write_csv(table, rows)


if __name__ == "__main__":
    main()
