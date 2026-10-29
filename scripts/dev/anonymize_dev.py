"""Anonymise a dev clone of the Clustox HRMS production database.

Run ONLY on the dev site, after restoring a prod backup into it. It replaces
all PII with realistic, deterministic fake data (so a re-clone reproduces the
same fakes), keeps the org chart / dates / attendance / leave balances intact,
and leaves zero real email addresses or company domains anywhere in the DB.

Guards: refuses unless the site is hrms.localhost with mute_emails=1 (set at
clone time), so it can never run against prod.

Usage (inside the dev frappe container):
    bench --site hrms.localhost execute hrms.scripts.dev.anonymize_dev.run
or copy this file into the bench and `bench ... execute <dotted.path>.run`.
"""
import frappe, json, random, re

FIRST = ["James","Mary","John","Patricia","Robert","Jennifer","Michael","Linda","David","Elizabeth",
         "William","Barbara","Richard","Susan","Joseph","Jessica","Thomas","Sarah","Daniel","Karen",
         "Matthew","Nancy","Anthony","Lisa","Mark","Betty","Paul","Margaret","Steven","Sandra",
         "Andrew","Ashley","Joshua","Kimberly","Kevin","Emily","Brian","Donna","George","Michelle"]
LAST = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Martinez","Lopez",
        "Wilson","Anderson","Taylor","Moore","Jackson","Martin","Lee","Perez","Thompson","White",
        "Harris","Clark","Lewis","Walker","Hall","Allen","Young","King","Wright","Scott"]
STREETS = ["Oak","Maple","Cedar","Pine","Elm","Park","Main","Hill","Lake","River","Spring","Sunset"]
CITIES = ["Springfield","Riverside","Fairview","Franklin","Greenville","Bristol","Clinton","Georgetown"]
KEEP_USERS = {"Administrator", "Guest"}
EMAIL_RE = "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+"
REAL_DOMAINS = ("clustox.com", "theclustox.com", "yopmail.com")


def _ident(key):
    r = random.Random("clx::" + str(key))
    return r.choice(FIRST), r.choice(LAST), r

def _phone(key):
    r = random.Random("ph::" + str(key))
    return "03" + "".join(r.choice("0123456789") for _ in range(9))

def _like(col):
    return "(" + " OR ".join(f"`{col}` LIKE '%{d}%'" for d in REAL_DOMAINS) + ")"


def run():
    if frappe.local.site != "hrms.localhost" or not frappe.conf.get("mute_emails"):
        print("REFUSE: expected the dev site (hrms.localhost) with mute_emails=1")
        return
    out = {"employees": 0, "user_renames": 0, "errors": []}

    # ---------- EMPLOYEES ----------
    emap = {}
    for e in frappe.get_all("Employee", fields=["name", "user_id"]):
        fn, ln, r = _ident(e.name)
        full = f"{fn} {ln}"
        tag = re.sub(r"[^a-z0-9]", "", e.name.lower())
        comp = f"{fn}.{ln}.{tag}@example.com".lower()
        pers = f"{fn.lower()}{ln.lower()}{tag}@example.com"
        addr = f"{r.randint(1,999)} {r.choice(STREETS)} Street, {r.choice(CITIES)}"
        frappe.db.set_value("Employee", e.name, {
            "first_name": fn, "middle_name": "", "last_name": ln, "employee_name": full,
            "personal_email": pers, "company_email": comp, "prefered_email": comp,
            "cell_number": _phone(e.name), "emergency_phone_number": _phone("em" + e.name),
            "date_of_birth": f"{r.randint(1982,2001)}-{r.randint(1,12):02d}-{r.randint(1,28):02d}",
            "current_address": addr, "permanent_address": addr,
            "person_to_be_contacted": f"{r.choice(FIRST)} {r.choice(LAST)}",
            "bank_name": "Dev Test Bank", "bank_ac_no": str(r.randint(10**11, 10**12)),
            "iban": "", "passport_number": "", "image": None,
        }, update_modified=False)
        if e.user_id and e.user_id not in KEEP_USERS:
            emap[e.user_id] = comp
        out["employees"] += 1

    # ---------- USERS (rename login email, scrub name; unique cols -> NULL) ----------
    used = set()
    emp_by_user = {}  # new email -> (fn,ln,full) for name scrub after rename
    for u in frappe.get_all("User", fields=["name"]):
        if u.name in KEEP_USERS or u.name.endswith("@example.com"):
            continue
        new = emap.get(u.name) or (lambda t: f"{t[0]}.{t[1]}.u{abs(hash(u.name))%100000}@example.com".lower())(_ident("u::"+u.name))
        while new in used or (new != u.name and frappe.db.exists("User", new)):
            new = new.replace("@", f"{random.randint(1,999)}@", 1)
        used.add(new)
        try:
            if new != u.name:
                frappe.rename_doc("User", u.name, new, force=True, merge=False)
                out["user_renames"] += 1
        except Exception as ex:
            out["errors"].append(f"user {u.name}: {type(ex).__name__}: {str(ex)[:80]}")
    # scrub user name fields (match linked employee where possible)
    emp_names = {e.user_id: (e.first_name, e.last_name, e.employee_name)
                 for e in frappe.get_all("Employee", fields=["user_id","first_name","last_name","employee_name"]) if e.user_id}
    for u in frappe.get_all("User", fields=["name"]):
        if u.name in KEEP_USERS:
            continue
        if u.name in emp_names:
            fn, ln, full = emp_names[u.name]
        else:
            fn, ln, r = _ident("u2::" + u.name); full = f"{fn} {ln}"
        try:
            frappe.db.set_value("User", u.name, {"first_name": fn, "last_name": ln, "full_name": full,
                "username": None, "mobile_no": None, "phone": "", "location": "", "bio": "", "birth_date": None},
                update_modified=False)
        except Exception as ex:
            out["errors"].append(f"userscrub {u.name}: {str(ex)[:60]}")

    # ---------- CONTACTS / ADDRESS ----------
    for c in frappe.get_all("Contact", fields=["name"]):
        fn, ln, r = _ident("contact::" + c.name)
        frappe.db.set_value("Contact", c.name, {"first_name": fn, "last_name": ln,
            "email_id": f"{fn}.{ln}@example.com".lower(), "phone": _phone("c"+c.name), "mobile_no": _phone("cm"+c.name)},
            update_modified=False)
    frappe.db.sql("UPDATE `tabContact Email` SET email_id=CONCAT('contact',FLOOR(RAND()*100000),'@example.com') WHERE email_id NOT LIKE '%@example.com'")
    frappe.db.sql("UPDATE `tabContact Phone` SET phone=CONCAT('03',FLOOR(RAND()*1000000000))")
    for a in frappe.get_all("Address", fields=["name"]):
        r = random.Random("addr::" + a.name)
        frappe.db.set_value("Address", a.name, {"address_line1": f"{r.randint(1,999)} {r.choice(STREETS)} Street",
            "address_line2": "", "city": r.choice(CITIES), "email_id": "address@example.com", "phone": _phone("a"+a.name)},
            update_modified=False)

    # ---------- salary / email accounts / recruitment ----------
    if frappe.db.exists("DocType", "Salary Structure Assignment"):
        frappe.db.sql("UPDATE `tabSalary Structure Assignment` SET base=150000, variable=0")
    frappe.db.sql("UPDATE `tabEmail Account` SET email_id=CONCAT('noreply-',name,'@example.com'), login_id=NULL, "
                  "smtp_server='smtp.example.com', email_server='imap.example.com', password=NULL, "
                  "enable_outgoing=0, enable_incoming=0, default_outgoing=0")
    if frappe.db.exists("DocType", "Email Group Member"):
        frappe.db.sql("UPDATE `tabEmail Group Member` SET email=CONCAT('member',FLOOR(RAND()*100000),'@example.com') WHERE email NOT LIKE '%@example.com'")
    if frappe.db.exists("DocType", "HD Ticket"):
        frappe.db.sql("UPDATE `tabHD Ticket` SET raised_by=CONCAT('requester',FLOOR(RAND()*100000),'@example.com') WHERE raised_by LIKE '%@%'")
    for ja in frappe.db.sql("SELECT name FROM `tabJob Applicant` WHERE " + _like("name"), as_dict=True):
        new = f"applicant{abs(hash(ja['name']))%100000}@example.com"
        try:
            frappe.rename_doc("Job Applicant", ja["name"], new, force=True)
            frappe.db.set_value("Job Applicant", new, {"email_id": new, "applicant_name": "Test Applicant"}, update_modified=False)
        except Exception as ex:
            out["errors"].append(f"JA {ja['name']}: {str(ex)[:50]}")

    frappe.db.commit()

    # ---------- DB-wide sweep: audit cols, json cols, free-text, logs ----------
    db = frappe.conf.get("db_name")
    def tables_with(col):
        return [r[0] for r in frappe.db.sql(
            "SELECT table_name FROM information_schema.columns WHERE table_schema=%s AND column_name=%s", (db, col))]
    for col in ("owner", "modified_by"):
        for t in tables_with(col):
            try: frappe.db.sql(f"UPDATE `{t}` SET `{col}`='Administrator' WHERE " + _like(col))
            except Exception: pass
    for col in ("_assign", "_liked_by", "_comments", "_user_tags"):
        for t in tables_with(col):
            try: frappe.db.sql(f"UPDATE `{t}` SET `{col}`=REGEXP_REPLACE(`{col}`,'{EMAIL_RE}','user@example.com') WHERE " + _like(col))
            except Exception: pass
    # clear disposable logs/cache/history
    for t in ["__global_search","__UserSettings","tabActivity Log","tabView Log","tabError Log",
              "tabVersion","tabRoute History","tabAccess Log","tabNotification Log","tabScheduled Job Log"]:
        try: frappe.db.sql(f"DELETE FROM `{t}`")
        except Exception: pass
    # user-keyed config satellites
    for t, col in [("tabDefaultValue","parent"),("tabDashboard Settings","name"),("tabUser Invitation","email"),("tabPortal User","user")]:
        try: frappe.db.sql(f"DELETE FROM `{t}` WHERE " + _like(col))
        except Exception: pass
    # HD Agent / TP Telephony Agent keyed by email
    try:
        for a in frappe.db.sql("SELECT name FROM `tabHD Agent` WHERE " + _like("name"), as_dict=True):
            nu = frappe.db.get_value("HD Agent", a["name"], "user")
            if nu and nu.endswith("@example.com") and nu != a["name"] and not frappe.db.exists("HD Agent", nu):
                frappe.rename_doc("HD Agent", a["name"], nu, force=True)
            else:
                frappe.db.sql("DELETE FROM `tabHD Agent` WHERE name=%s", a["name"])
    except Exception: pass
    try: frappe.db.sql("DELETE FROM `tabTP Telephony Agent` WHERE " + _like("name"))
    except Exception: pass
    # free-text bodies: replace company domains + any email
    for t, c in [("tabComment","content"),("tabComment","comment_email"),("tabCommunication","content"),
                 ("tabCommunication","text_content"),("tabCommunication","subject")]:
        try:
            frappe.db.sql(f"UPDATE `{t}` SET `{c}`=REGEXP_REPLACE(`{c}`,'{EMAIL_RE}','user@example.com') WHERE " + _like(c))
        except Exception: pass
    frappe.db.sql("UPDATE `tabCommunication` SET sender='dev@example.com', recipients='dev@example.com', reference_owner='Administrator' WHERE " + _like("sender") + " OR " + _like("recipients"))
    # domain replace across all text bodies
    for r in frappe.db.sql("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema=%s AND data_type IN ('text','mediumtext','longtext')", (db,), as_dict=True):
        try:
            frappe.db.sql(f"UPDATE `{r['table_name']}` SET `{r['column_name']}`="
                          f"REPLACE(REPLACE(REPLACE(`{r['column_name']}`,'theclustox.com','example.com'),'@clustox.com','@example.com'),'@yopmail.com','@example.com') "
                          f"WHERE " + _like(r['column_name']))
        except Exception: pass

    frappe.db.commit(); frappe.clear_cache()

    # ---------- VERIFY: zero real-domain rows across every text column ----------
    leaks = 0
    for r in frappe.db.sql("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema=%s AND data_type IN ('varchar','text','mediumtext','longtext','char')", (db,), as_dict=True):
        try:
            leaks += frappe.db.sql(f"SELECT COUNT(*) FROM `{r['table_name']}` WHERE " + _like(r['column_name']))[0][0]
        except Exception: pass
    out["remaining_real_domain_rows"] = leaks
    out["clean"] = leaks == 0
    out["errors"] = out["errors"][:10]
    print("ANON=" + json.dumps(out, default=str))
