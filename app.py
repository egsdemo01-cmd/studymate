# StudyMate - Class 12 Student Study & Exam Management Portal (Flask + SQLite)
import sqlite3, os
from datetime import date
from functools import wraps
from flask import Flask, render_template, request, redirect, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-key"          # needed for sessions
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "studymate.db")

# ---------- DATABASE (9 tables; user_id is the foreign key linking data to a student) ----------
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT DEFAULT 'student');
CREATE TABLE IF NOT EXISTS profiles(user_id INTEGER PRIMARY KEY REFERENCES users(id), name TEXT, class TEXT, school TEXT, roll TEXT, email TEXT, about TEXT);
CREATE TABLE IF NOT EXISTS subjects(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id), name TEXT NOT NULL, teacher TEXT);
CREATE TABLE IF NOT EXISTS marks(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id), subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE, exam TEXT, obtained REAL, total REAL);
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id), title TEXT, priority TEXT, deadline TEXT, done TEXT DEFAULT '0');
CREATE TABLE IF NOT EXISTS timetable(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id), subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE, date TEXT, start TEXT, end TEXT, topic TEXT);
CREATE TABLE IF NOT EXISTS exams(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id), name TEXT, subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE, date TEXT);
CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id), subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE, title TEXT, content TEXT);
CREATE TABLE IF NOT EXISTS study_progress(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id), subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE, done INTEGER, remaining INTEGER, hours REAL);
"""

def db():                                   # one connection per request
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row      # rows behave like dictionaries
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close_db(e):
    d = g.pop("db", None)
    if d: d.close()

def init_db():                              # creates tables + a demo teacher account
    con = sqlite3.connect(DB); con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM users WHERE username='teacher'").fetchone():
        con.execute("INSERT INTO users(username,password_hash,role) VALUES('teacher',?,'teacher')",
                    (generate_password_hash("teacher123"),))
    con.commit(); con.close()

# ---------- LOGIN HELPERS ----------
def login_required(f):                      # decorator: blocks pages if not logged in
    @wraps(f)
    def wrapper(*a, **k):
        if "uid" not in session:
            return redirect("/login")
        return f(*a, **k)
    return wrapper

@app.route("/")
def home():
    return redirect("/dashboard" if "uid" in session else "/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = db().execute("SELECT * FROM users WHERE username=?", (request.form["username"].strip(),)).fetchone()
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session["uid"], session["role"], session["user"] = u["id"], u["role"], u["username"]
            return redirect("/admin" if u["role"] == "teacher" else "/dashboard")
        flash("Wrong username or password")
    return render_template("auth.html", register=False)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name, user, pw = request.form["name"].strip(), request.form["username"].strip(), request.form["password"]
        if len(pw) < 6 or not user or not name:
            flash("Fill all fields; password needs 6+ characters")
        elif db().execute("SELECT 1 FROM users WHERE username=?", (user,)).fetchone():
            flash("Username already taken")
        else:
            cur = db().execute("INSERT INTO users(username,password_hash) VALUES(?,?)", (user, generate_password_hash(pw)))
            uid = cur.lastrowid
            db().execute("INSERT INTO profiles(user_id,name,class) VALUES(?,?,'12')", (uid, name))
            for s in ["English", "Physics", "Chemistry", "Mathematics", "Computer Science"]:   # sample subjects
                db().execute("INSERT INTO subjects(user_id,name) VALUES(?,?)", (uid, s))
            db().commit(); flash("Registered! Please login."); return redirect("/login")
    return render_template("auth.html", register=True)

@app.route("/logout")
def logout():
    session.clear(); return redirect("/login")

# ---------- GENERIC CRUD MODULES ----------
# Each module: title, icon, fields [(column, label, type, options)], ORDER BY.  Same code serves all of them.
PRI = [("High", "High"), ("Medium", "Medium"), ("Low", "Low")]
MODULES = {
 "subjects":  ("Subjects", "📚", [("name","Subject name","text"),("teacher","Teacher","text")], "id"),
 "marks":     ("Marks", "📝", [("subject_id","Subject","subject"),("exam","Exam (e.g. Unit Test 1)","text"),("obtained","Marks obtained","number"),("total","Maximum marks","number")], "id DESC"),
 "timetable": ("Timetable", "🗓️", [("subject_id","Subject","subject"),("date","Date","date"),("start","Start","time"),("end","End","time"),("topic","Topic","text")], "date, start"),
 "tasks":     ("Tasks", "✅", [("title","Task","text"),("priority","Priority","select",PRI),("deadline","Deadline","date"),("done","Status","select",[("0","Pending"),("1","Completed")])], "done, deadline"),
 "exams":     ("Exams", "⏳", [("name","Exam name","text"),("subject_id","Subject","subject"),("date","Exam date","date")], "date"),
 "notes":     ("Notes", "📓", [("subject_id","Subject","subject"),("title","Title","text"),("content","Content","textarea")], "id DESC"),
 "study_progress": ("Progress", "📈", [("subject_id","Subject","subject"),("done","Topics completed","number"),("remaining","Topics remaining","number"),("hours","Study hours","number")], "id DESC"),
}
@app.context_processor
def inject_modules():
    return {"modules": MODULES}

EXTRA_HEAD = {"marks": "Percent", "exams": "Days left", "study_progress": "Progress"}

def extra(mod, r):                          # computed column for some modules
    if mod == "marks":
        return f"{r['obtained'] / r['total'] * 100:.1f}%" if r["total"] else "-"
    if mod == "exams":
        d = (date.fromisoformat(r["date"]) - date.today()).days
        return f"{d} days" if d >= 0 else "Over"
    if mod == "study_progress":
        t = r["done"] + r["remaining"]
        return f"{r['done'] / t * 100:.0f}%" if t else "0%"
    return ""

def marks_summary(uid):                     # subject %, overall %, total, average, best, worst
    rows = db().execute("SELECT s.name, SUM(m.obtained) o, SUM(m.total) t FROM marks m JOIN subjects s ON s.id=m.subject_id WHERE m.user_id=? GROUP BY s.id", (uid,)).fetchall()
    per = [(r["name"], round(r["o"] / r["t"] * 100, 1)) for r in rows if r["t"]]
    if not per: return None
    O, T = sum(r["o"] for r in rows), sum(r["t"] for r in rows)
    return dict(per=per, total=O, out_of=T, avg=round(O / len(per), 1), overall=round(O / T * 100, 1),
                best=max(per, key=lambda x: x[1]), worst=min(per, key=lambda x: x[1]))

@app.route("/m/<mod>")
@login_required
def module(mod):
    if mod not in MODULES: return redirect("/dashboard")
    title, icon, fields, order = MODULES[mod]
    uid, q = session["uid"], request.args.get("q", "").lower()
    subs = db().execute("SELECT * FROM subjects WHERE user_id=?", (uid,)).fetchall()
    if not any(f[2] == "subject" for f in fields):      # subjects & tasks have no subject column
        sql = f"SELECT * FROM {mod} WHERE user_id=? ORDER BY {order}"
    else:
        sql = f"SELECT t.*, s.name AS subject_name FROM {mod} t LEFT JOIN subjects s ON s.id=t.subject_id WHERE t.user_id=? ORDER BY {order}"
    rows = []
    for r in db().execute(sql, (uid,)).fetchall():
        r = dict(r); view = []
        for f in fields:                    # build the text shown in each table cell
            if f[2] == "subject": view.append(r["subject_name"])
            elif f[2] == "select": view.append(dict(f[3]).get(str(r[f[0]]), r[f[0]]))
            else: view.append(r[f[0]])
        r["view"], r["extra"] = view, extra(mod, r)
        if q and q not in " ".join(str(v).lower() for v in view): continue   # search filter
        rows.append(r)
    edit = None
    if request.args.get("edit"):
        edit = db().execute(f"SELECT * FROM {mod} WHERE id=? AND user_id=?", (request.args["edit"], uid)).fetchone()
    return render_template("module.html", mod=mod, title=title, icon=icon, fields=fields, rows=rows, subs=subs,
                           edit=edit, q=q, extra_head=EXTRA_HEAD.get(mod),
                           summary=marks_summary(uid) if mod == "marks" else None)

@app.route("/m/<mod>/save", methods=["POST"])
@login_required
def save(mod):                              # handles both ADD (insert) and EDIT (update)
    if mod not in MODULES: return redirect("/dashboard")
    fields, uid, rid = MODULES[mod][2], session["uid"], request.form.get("id")
    cols = [f[0] for f in fields]
    vals = [request.form.get(c, "").strip() for c in cols]
    if any(v == "" for c, v in zip(cols, vals) if c != "teacher"):
        flash("Please fill all fields"); return redirect(f"/m/{mod}")
    if mod == "marks" and float(vals[2]) > float(vals[3]):
        flash("Obtained marks cannot exceed maximum marks"); return redirect("/m/marks")
    if rid:
        sets = ",".join(c + "=?" for c in cols)
        db().execute(f"UPDATE {mod} SET {sets} WHERE id=? AND user_id=?", vals + [rid, uid])
    else:
        db().execute(f"INSERT INTO {mod}(user_id,{','.join(cols)}) VALUES(?,{','.join('?' * len(cols))})", [uid] + vals)
    db().commit(); flash("Saved successfully")
    return redirect(f"/m/{mod}")

@app.route("/m/<mod>/delete/<int:rid>", methods=["POST"])
@login_required
def delete(mod, rid):
    if mod in MODULES:
        db().execute(f"DELETE FROM {mod} WHERE id=? AND user_id=?", (rid, session["uid"])); db().commit()
    return redirect(f"/m/{mod}")

# ---------- DASHBOARD ----------
@app.route("/dashboard")
@login_required
def dashboard():
    uid, today = session["uid"], date.today().isoformat()
    one = lambda sql, *a: db().execute(sql, a).fetchone()
    p = one("SELECT * FROM profiles WHERE user_id=?", uid)
    exams = db().execute("SELECT e.*, s.name sub FROM exams e JOIN subjects s ON s.id=e.subject_id WHERE e.user_id=? AND e.date>=? ORDER BY e.date", (uid, today)).fetchall()
    exams = [dict(e, days=(date.fromisoformat(e["date"]) - date.today()).days) for e in exams]
    pr = one("SELECT COALESCE(SUM(done),0) d, COALESCE(SUM(remaining),0) r, COALESCE(SUM(hours),0) h FROM study_progress WHERE user_id=?", uid)
    total = pr["d"] + pr["r"]
    return render_template("dashboard.html", p=p, exams=exams,
        n_sub=one("SELECT COUNT(*) FROM subjects WHERE user_id=?", uid)[0],
        pending=one("SELECT COUNT(*) FROM tasks WHERE user_id=? AND done='0'", uid)[0],
        progress=round(pr["d"] / total * 100) if total else 0, hours=pr["h"], summary=marks_summary(uid))

# ---------- PROFILE ----------
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        f = request.form
        db().execute("UPDATE profiles SET name=?,class=?,school=?,roll=?,email=?,about=? WHERE user_id=?",
                     (f["name"], f["class"], f["school"], f["roll"], f["email"], f["about"], session["uid"]))
        db().commit(); flash("Profile updated")
    p = db().execute("SELECT * FROM profiles WHERE user_id=?", (session["uid"],)).fetchone()
    return render_template("profile.html", p=p)

# ---------- TEACHER / ADMIN DEMO PANEL (login: teacher / teacher123) ----------
@app.route("/admin")
@login_required
def admin():
    if session.get("role") != "teacher": return redirect("/dashboard")
    students = db().execute("""SELECT u.username, p.name, p.roll,
        (SELECT COUNT(*) FROM subjects WHERE user_id=u.id) subjects,
        (SELECT COUNT(*) FROM tasks WHERE user_id=u.id AND done='0') pending,
        (SELECT ROUND(SUM(obtained)*100.0/SUM(total),1) FROM marks WHERE user_id=u.id) percent,
        (SELECT COALESCE(SUM(hours),0) FROM study_progress WHERE user_id=u.id) hours
        FROM users u JOIN profiles p ON p.user_id=u.id WHERE u.role='student'""").fetchall()
    return render_template("admin.html", students=students)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
