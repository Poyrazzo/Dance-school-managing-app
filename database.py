import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import os
import unicodedata, difflib



def _fold_text(s: str) -> str:
    """Lowercase, strip, remove diacritics, collapse spaces for stable matching."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().strip()
    s = " ".join(s.split())  # collapse multiple spaces
    return s

def normalize_class_key(name: str) -> str:
    folded = _fold_text(name)
    # collapse multiple spaces to one, but keep a single space
    collapsed = " ".join(folded.split())
    return collapsed  # DON'T remove spaces entirely


def resolve_canonical_class_name(input_name: str) -> str:
    """
    If an existing class is a close match (case-insensitive, typo-tolerant),
    return its canonical stored name; otherwise return the original input_name.
    """
    wanted_key = normalize_class_key(input_name)
    existing = get_unique_class_names()  # current names as stored (canonical forms)
    if not existing:
        return input_name

    # 1) exact key match → snap to that canonical name
    key_to_canon = {normalize_class_key(n): n for n in existing}
    if wanted_key in key_to_canon:
        return key_to_canon[wanted_key]

    # 2) fuzzy match on folded text
    folded_to_canon = {_fold_text(n): n for n in existing}
    choices = list(folded_to_canon.keys())
    # cutoff ~0.78 works well for small typos: "bachta" ~ "bachata"
    match = difflib.get_close_matches(_fold_text(input_name), choices, n=1, cutoff=0.78)
    if match:
        return folded_to_canon[match[0]]

    # no match → treat as a new class name
    return input_name

def _ensure_order_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS class_order (
            name_key TEXT PRIMARY KEY,
            position INTEGER
        )
    """)

def _norm_tr(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.strip().lower()
    tr = {"î":"i","â":"a","û":"u","ı":"i","ğ":"g","ş":"s","ç":"c","ö":"o","ü":"u",
          "İ":"i","Ğ":"g","Ş":"s","Ç":"c","Ö":"o","Ü":"u"}
    for k, v in tr.items():
        s = s.replace(k, v)
    return s

_DAY_ALIAS = {
    "pzt": 0, "pazartesi": 0, "pztesi": 0, "pzt.": 0,
    "salı": 1, "sali": 1,
    "çarşamba": 2, "carsamba": 2, "çarsamba": 2,
    "perşembe": 3, "persembe": 3, "perş": 3,
    "cuma": 4,
    "cmrtsi": 5, "cumartesi": 5, "cmt": 5, "cts": 5,
    "pazar": 6
}

def _day_token_to_index(token: str):
    return _DAY_ALIAS.get(_norm_tr(token))


def save_class_tab_order(order_keys):
    conn = get_connection()
    cur = conn.cursor()
    _ensure_order_table(cur)
    for pos, key in enumerate(order_keys):
        cur.execute("""
            INSERT INTO class_order (name_key, position)
            VALUES (?, ?)
            ON CONFLICT(name_key) DO UPDATE SET position=excluded.position
        """, (key, pos))
    conn.commit()
    conn.close()


def _linux_desktop_dir() -> Path:
    """Find the Desktop dir on Linux respecting XDG user-dirs; fall back sanely."""
    home = Path.home()
    # 1) XDG user-dirs config
    cfg = home / ".config" / "user-dirs.dirs"
    if cfg.exists():
        try:
            for line in cfg.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("XDG_DESKTOP_DIR"):
                    # e.g. XDG_DESKTOP_DIR="$HOME/Desktop"
                    _, rhs = line.split("=", 1)
                    path_str = rhs.strip().strip('"')
                    path_str = path_str.replace("$HOME", str(home))
                    return Path(os.path.expandvars(path_str))
        except Exception:
            pass

    # 2) Common localized names
    for name in ("Desktop", "Masaüstü", "Escritorio", "Bureau", "Рабочий стол"):
        p = home / name
        if p.exists():
            return p

    # 3) Last resort: ~/Desktop (create if missing)
    return home / "Desktop"

def get_storage_root() -> Path:
    """
    Cross-platform storage root under the user's Desktop called '111'.
    Windows/macOS: ~/Desktop/111
    Linux: respects XDG desktop dir; falls back to ~/Desktop/111
    """
    if os.name == "posix" and "linux" in os.uname().sysname.lower():
        desktop = _linux_desktop_dir()
    else:
        desktop = Path.home() / "Desktop"

    root = desktop / "111"
    root.mkdir(parents=True, exist_ok=True)
    return root


DB_PATH = Path(__file__).resolve().with_name("dance_school.db")


def get_db_path() -> Path:
    return DB_PATH


def get_connection():
    return sqlite3.connect(str(DB_PATH))

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            day TEXT NOT NULL,
            hour TEXT NOT NULL,
            price REAL
        )
    ''')

    # === Migration: add name_key and unique index for de-duplication ===
    try:
        cursor.execute("ALTER TABLE classes ADD COLUMN name_key TEXT")
    except Exception:
        pass  # column might already exist

    # backfill name_key for all rows
    cursor.execute("SELECT id, name FROM classes WHERE name_key IS NULL OR name_key=''")
    for cid, cname in cursor.fetchall():
        cursor.execute("UPDATE classes SET name_key=? WHERE id=?", (normalize_class_key(cname), cid))

    cursor.execute("""
        DELETE FROM classes
        WHERE id NOT IN (
            SELECT MIN(id) FROM classes
            GROUP BY name_key, day, hour
        )
    """)


    # unique index on name_key + day + hour (so same class group can have multiple day/hour)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_classes_namekey_day_hour
        ON classes(name_key, day, hour)
    """)

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            number TEXT,
            start_time TEXT,
            end_time TEXT,
            left_classes INTEGER,
            info TEXT,
            discount_info TEXT,
            class_id INTEGER,
            FOREIGN KEY (class_id) REFERENCES classes(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            date TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    ''')

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hesap_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isim TEXT,
            miktar REAL,
            odeme_sekli TEXT,
            ders TEXT,
            notlar TEXT
        )
    """)
    # Create the table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kasa_table (
            id INTEGER PRIMARY KEY,
            eski_kasa REAL
        )
    ''')
    
    conn.commit()
    conn.close()


def get_unique_class_names():
    conn = get_connection()
    cur = conn.cursor()
    _ensure_order_table(cur)
    cur.execute("""
        SELECT MIN(c.name) AS display_name
        FROM classes c
        GROUP BY c.name_key
    """)
    names = [row[0] for row in cur.fetchall()]

    # fetch saved order
    cur.execute("SELECT name_key, position FROM class_order")
    order_map = dict(cur.fetchall())

    # sort by saved position first, then by name as fallback
    def sort_key(n):
        key = normalize_class_key(n)
        return (order_map.get(key, 10**9), n.lower())

    names.sort(key=sort_key)
    conn.close()
    return names


# === ESKİLER helpers ===

def get_class_group_key_by_id(class_id):
    """Return (name_key, canonical_name) for a given class_id."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name_key, name FROM classes WHERE id=?", (class_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None, None
    return row[0], row[1]

def ensure_eskiler_class(class_name):
    """
    Ensure there is a classes-row for this group named 'ESKİLER' (day=hour='ESKİLER').
    Return its class_id.
    """
    canon = resolve_canonical_class_name(class_name)
    name_key = normalize_class_key(canon)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM classes
        WHERE name_key=? AND day='ESKİLER' AND hour='ESKİLER'
    """, (name_key,))
    row = cur.fetchone()
    if row:
        conn.close()
        return row[0]

    cur.execute("""
        INSERT INTO classes (name, day, hour, price, name_key)
        VALUES (?, 'ESKİLER', 'ESKİLER', NULL, ?)
    """, (canon, name_key))
    esk_id = cur.lastrowid
    conn.commit()
    conn.close()
    return esk_id

def student_exists_in_class_by_name_or_number(target_class_id, name, number):
    """
    Return True if a student with same (normalized) name OR phone (spaces ignored)
    already exists in target_class_id.
    """
    from utils import tr_norm
    key_name = tr_norm(name or "")
    key_num  = "".join((number or "").split())

    conn = get_connection()
    cur = conn.cursor()
    # name check (TR-normalized, spaces removed)
    cur.execute("""
        SELECT COUNT(1)
        FROM students
        WHERE class_id=?
          AND (
                REPLACE(
                  REPLACE(
                  REPLACE(
                  REPLACE(
                  REPLACE(
                  REPLACE(
                  REPLACE(LOWER(name),
                    '̇',''),'ı','i'),'ş','s'),'ğ','g'),'ö','o'),'ü','u'),'ç','c'),
                ' ', ''
                ) = ?
               OR REPLACE(IFNULL(number,''), ' ', '') = ?
              )
    """, (target_class_id, key_name, key_num))
    exists = cur.fetchone()[0] > 0
    conn.close()
    return exists

def move_student_to_class(student_id, target_class_id):
    """Update the student's class_id to target_class_id."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE students SET class_id=? WHERE id=?", (target_class_id, student_id))
    conn.commit()
    conn.close()

def add_class(name, day, hour, price):
    canon = resolve_canonical_class_name(name)
    name_key = normalize_class_key(canon)

    conn = get_connection()
    cursor = conn.cursor()
    # Will raise if exact (name_key, day, hour) already exists
    cursor.execute(
        "INSERT INTO classes (name, day, hour, price, name_key) VALUES (?, ?, ?, ?, ?)",
        (canon, day, hour, price, name_key)
    )
    conn.commit()
    conn.close()

def get_class_times_by_name(name):
    canon = resolve_canonical_class_name(name)
    key = normalize_class_key(canon)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT day, hour FROM classes WHERE name_key=? ORDER BY day, hour", (key,))
    results = cursor.fetchall()
    conn.close()
    return results


def delete_class_instance(name, day, hour):
    canon = resolve_canonical_class_name(name)
    key = normalize_class_key(canon)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM classes WHERE name_key=? AND day=? AND hour=?", (key, day, hour))
    conn.commit()
    conn.close()


def get_class_id(name, day, hour):
    canon = resolve_canonical_class_name(name)
    key = normalize_class_key(canon)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM classes WHERE name_key=? AND day=? AND hour=?",
        (key, day, hour)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_students_by_class_id(class_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, number, start_time, end_time, left_classes, info FROM students WHERE class_id=?",
        (class_id,)
    )
    results = cursor.fetchall()
    conn.close()
    return results

def add_student_to_class(class_id, name, number, start_date, note, left_classes):
    conn = get_connection()
    cursor = conn.cursor()

    # Calculate end_time as 28 days after start_date
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = start_dt + timedelta(days=28)
    end_time = end_dt.strftime("%Y-%m-%d")
    
    cursor.execute(
        '''
        INSERT INTO students (class_id, name, number, start_time, end_time, left_classes, info)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        (class_id, name, number, start_date, end_time, left_classes, note)
    )
    conn.commit()
    conn.close()


def delete_student(student_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students WHERE id=?", (student_id,))
    conn.commit()
    conn.close()

def update_student_info(student_id, name, number, start_time, note):
    # Use today as fallback if start_time is empty
    if not start_time.strip():
        start_dt = datetime.today()
    else:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''UPDATE students
           SET name=?, number=?, start_time=?, info=?
           WHERE id=?''',
        (name, number, start_dt.strftime("%Y-%m-%d"), note, student_id)
    )
    conn.commit()
    conn.close()
    print(f"[DEBUG] Updated student (id={student_id}): name={name}, number={number}, start_date={start_dt}, note={note}. End date NOT touched.")



def class_instance_exists(name, day, hour):
    canon = resolve_canonical_class_name(name)
    key = normalize_class_key(canon)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM classes WHERE name_key=? AND day=? AND hour=?",
        (key, day, hour)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def update_class_instance(class_name, old_day, old_hour, new_day, new_hour):
    conn = get_connection()
    try:
        cur  = conn.cursor()
        name_key = normalize_class_key(class_name)

        if (old_day == new_day) and (old_hour == new_hour):
            return 0

        cur.execute("""
            SELECT id FROM classes
            WHERE name_key=? AND day=? AND hour=?
        """, (name_key, new_day, new_hour))
        if cur.fetchone():
            raise ValueError("duplicate_class_time")

        cur.execute("""
            UPDATE classes
            SET day=?, hour=?
            WHERE name_key=? AND day=? AND hour=?
        """, (new_day, new_hour, name_key, old_day, old_hour))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def update_left_classes_for_all_students():
    today = datetime.today().date()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT students.id, students.start_time, students.end_time, students.left_classes, classes.day
        FROM students
        JOIN classes ON students.class_id = classes.id
    ''')
    rows = cursor.fetchall()

    for student_id, start_time_str, end_time_str, left_classes, class_days in rows:
        if not start_time_str.strip() or not end_time_str.strip():
            continue

        try:
            start_date = datetime.strptime(start_time_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_time_str, "%Y-%m-%d").date()
        except Exception as e:
            print("[DEBUG] Date parse error:", e)
            continue

        class_days_list = [d.strip() for d in (class_days or "").split(",") if d.strip()]
        class_day_indexes = []
        for d in class_days_list:
            idx = _day_token_to_index(d)
            if idx is not None:
                class_day_indexes.append(idx)


        # Count total classes from start date up to (but not including) end date
        total_classes = 0
        current_date = start_date
        while current_date < end_date:
            if current_date.weekday() in class_day_indexes:
                total_classes += 1
            current_date += timedelta(days=1)

        # Count classes that have passed up to TODAY, not including end_date
        classes_passed = 0
        current_date = start_date
        while current_date <= today and current_date < end_date:
            if current_date.weekday() in class_day_indexes:
                classes_passed += 1
            current_date += timedelta(days=1)

        new_left_classes = max(total_classes - classes_passed, 0)

        # If today is after end_date, subtract for every class day that passed after end_date
        if today > end_date:
            after_end_date = end_date + timedelta(days=1)
            while after_end_date <= today:
                if after_end_date.weekday() in class_day_indexes:
                    new_left_classes -= 1
                after_end_date += timedelta(days=1)
            # Left classes can be negative
            # no clamping to zero here
            # because you said "should be negative when today is after end"
            # so skip: new_left_classes = max(new_left_classes, 0)

        # Debug info
        """print(f"[DEBUG] Student {student_id} -> Start: {start_date}, End: {end_date}, "
              f"ClassDays: {class_days_list}, Total: {total_classes}, "
              f"Passed: {classes_passed}, Left: {new_left_classes}")"""

        cursor.execute(
            "UPDATE students SET left_classes=? WHERE id=?",
            (new_left_classes, student_id)
        )

    conn.commit()
    conn.close()

def extend_student_courses_in_db(student_id, additional_courses, new_end_date):
    conn = get_connection()
    cursor = conn.cursor()

    # Fetch current left_classes and current end_time (if needed)
    cursor.execute("SELECT left_classes FROM students WHERE id=?", (student_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        return

    current_left_classes = result[0]
    new_left_classes = current_left_classes + additional_courses

    # Save the updated left_classes and new end_date
    cursor.execute(
        "UPDATE students SET left_classes=?, end_time=? WHERE id=?",
        (new_left_classes, new_end_date, student_id)
    )
    conn.commit()
    conn.close()


def get_days_of_class(class_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT day FROM classes WHERE id=?", (class_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return ""

def update_student_info_full(student_id, name, number, start_time, end_time, left_classes, note):
    conn = get_connection()
    cursor = conn.cursor()

    # Load current end_time from DB
    cursor.execute("SELECT end_time FROM students WHERE id=?", (student_id,))
    current_end_time = cursor.fetchone()[0]

    # Only update end_time if it's different from what’s in DB
    if end_time != current_end_time:
        #print(f"[DEBUG] update_student_info_full: Changing end_time from {current_end_time} to {end_time}")
        cursor.execute(
            '''UPDATE students
               SET name=?, number=?, start_time=?, end_time=?, left_classes=?, info=?
               WHERE id=?''',
            (name, number, start_time, end_time, left_classes, note, student_id)
        )
    else:
        #print(f"[DEBUG] update_student_info_full: end_time unchanged ({current_end_time})")
        cursor.execute(
            '''UPDATE students
               SET name=?, number=?, start_time=?, left_classes=?, info=?
               WHERE id=?''',
            (name, number, start_time, left_classes, note, student_id)
        )

    conn.commit()
    conn.close()



def update_student_end_date(student_id, new_end_date):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE students SET end_time=? WHERE id=?",
        (new_end_date, student_id)
    )
    conn.commit()
    conn.close()
    print(f"[DEBUG] update_student_end_date: Updated end_time to {new_end_date} for student {student_id}")


def add_attendance(student_id, date_str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO attendance (student_id, date) VALUES (?, ?)",
        (student_id, date_str)
    )
    conn.commit()
    conn.close()

def get_attendance_for_student(student_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT date FROM attendance WHERE student_id = ? ORDER BY date",
        (student_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def update_student_left_classes(student_id, new_left_classes):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE students SET left_classes=? WHERE id=?",
        (new_left_classes, student_id)
    )
    conn.commit()
    conn.close()

def remove_attendance_for_student(student_id, date_str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM attendance WHERE student_id=? AND date=?",
        (student_id, date_str)
    )
    conn.commit()
    conn.close()

def delete_attendance(student_id, date_str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM attendance WHERE student_id = ? AND date = ?",
        (student_id, date_str)
    )
    conn.commit()
    conn.close()

# 🔥 Hesap records functions

def get_all_hesap_records():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT isim, miktar, odeme_sekli, ders, notlar FROM hesap_records")
    rows = cursor.fetchall()
    conn.close()
    return rows

def save_all_hesap_records(rows_data):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM hesap_records")  # Clear existing
    for row in rows_data:
        cursor.execute("""
            INSERT INTO hesap_records (isim, miktar, odeme_sekli, ders, notlar)
            VALUES (?, ?, ?, ?, ?)
        """, row)
    conn.commit()
    conn.close()

def update_student_start_time_only(student_id, new_start_time):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''UPDATE students
           SET start_time=?
           WHERE id=?''',
        (new_start_time, student_id)
    )
    conn.commit()
    conn.close()
    print(f"[DEBUG] update_student_start_time_only: Updated start_time for student {student_id} to {new_start_time}")


def add_student_back(student, class_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO students
        (id, name, number, start_time, end_time, left_classes, info, discount_info, class_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        student[0], student[1], student[2], student[3], student[4],
        student[5], student[6], "", class_id
    ))
    conn.commit()
    conn.close()

# database.py
def get_students_with_zero_kalan_gun():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.id, s.name, s.number, s.start_time, s.end_time, c.name
        FROM students s
        JOIN classes c ON s.class_id = c.id
    ''')
    students = cursor.fetchall()
    conn.close()

    zero_kalan_students = []
    today = datetime.today().date()

    for student_id, name, number, start_str, end_str, class_name in students:
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
            kalan_gun = (end_date - today).days
            if kalan_gun == 0:
                zero_kalan_students.append((student_id, name, number, class_name))
        except Exception as e:
            print(f"[DEBUG] Error parsing dates for student {student_id}: {e}")
            continue

    return zero_kalan_students

def search_students_by_name_or_number(search_text):
    from utils import tr_norm
    conn = get_connection()
    cursor = conn.cursor()

    norm = tr_norm(search_text)
    digits = "".join(ch for ch in str(search_text) if ch.isdigit())

    # normalize, then remove spaces inside SQL to match tr_norm behavior
    name_norm_sql = """
        REPLACE(
          REPLACE(
          REPLACE(
          REPLACE(
          REPLACE(
          REPLACE(
          REPLACE(LOWER(s.name),
              '̇',''),   -- U+0307 combining dot above
              'ı','i'),
              'ş','s'),
              'ğ','g'),
              'ö','o'),
              'ü','u'),
              'ç','c'),
          ' ', ''      -- 🔧 remove spaces to align with tr_norm
        )
    """

    where = f"({name_norm_sql} LIKE ?)"
    params = [f"%{norm}%"]

    if digits:
        # also remove spaces from number before LIKE to be forgiving
        where += " OR REPLACE(s.number,' ','') LIKE ?"
        params.append(f"%{digits}%")

    sql = f"""
        SELECT s.id, s.name, s.number, c.name, c.day, c.hour
        FROM students s
        JOIN classes c ON s.class_id = c.id
        WHERE {where}
        ORDER BY s.name COLLATE NOCASE
    """
    cursor.execute(sql, params)
    results = cursor.fetchall()
    conn.close()
    return results




def save_eski_kasa(eski_kasa_value):
    conn = get_connection()
    cursor = conn.cursor()

    # Clear previous entries (to keep it as a single value)
    cursor.execute("DELETE FROM kasa_table")

    # Insert the new value
    cursor.execute("INSERT INTO kasa_table (eski_kasa) VALUES (?)", (eski_kasa_value,))

    conn.commit()
    conn.close()

def get_eski_kasa():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT eski_kasa FROM kasa_table ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def update_student_left_classes_based_on_single_day(student_id, single_day):
    idx = _day_token_to_index(single_day)
    if idx is None:
        print("[DEBUG] Selected day not recognized:", single_day)
        return
    target_day_idx = idx

    if target_day_idx is None:
        print("[DEBUG] Selected day not recognized.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT start_time, end_time FROM students WHERE id=?", (student_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return

    start_date = datetime.strptime(row[0], "%Y-%m-%d").date()
    end_date = datetime.strptime(row[1], "%Y-%m-%d").date()
    today = datetime.today().date()

    # Count total classes for this day
    total_classes = 0
    current_date = start_date
    while current_date < end_date:
        if current_date.weekday() == target_day_idx:
            total_classes += 1
        current_date += timedelta(days=1)

    # Count passed classes up to today
    classes_passed = 0
    current_date = start_date
    while current_date <= today and current_date < end_date:
        if current_date.weekday() == target_day_idx:
            classes_passed += 1
        current_date += timedelta(days=1)

    left_classes = total_classes - classes_passed

    # Allow negative values if today is past end_date
    if today > end_date:
        after_end_date = end_date + timedelta(days=1)
        while after_end_date <= today:
            if after_end_date.weekday() == target_day_idx:
                left_classes -= 1
            after_end_date += timedelta(days=1)

    print(f"[DEBUG] Updated single-day left_classes for student {student_id}: {left_classes}")

    cursor.execute(
        "UPDATE students SET left_classes=? WHERE id=?",
        (left_classes, student_id)
    )
    conn.commit()
    conn.close()

def add_student_to_class_with_dates(class_id, name, number, start_date, end_date, note, left_classes):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT INTO students (class_id, name, number, start_time, end_time, left_classes, info)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        (class_id, name, number, start_date, end_date, left_classes, note)
    )
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def get_students_by_ids(ids):
    """Return full student rows for the given id list."""
    if not ids:
        return []
    conn = get_connection()
    cursor = conn.cursor()
    qmarks = ",".join("?" for _ in ids)
    cursor.execute(f"""
        SELECT id, class_id, name, number, start_time, end_time, left_classes, info
        FROM students
        WHERE id IN ({qmarks})
        ORDER BY id
    """, ids)
    rows = cursor.fetchall()
    conn.close()
    return rows


def restore_students(rows):
    """
    Reinsert students as they were (keeps original IDs).
    Each row must be: (id, class_id, name, number, start_time, end_time, left_classes, info)
    """
    if not rows:
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT OR REPLACE INTO students
        (id, class_id, name, number, start_time, end_time, left_classes, info)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    conn.close()

def get_all_class_instances():
    """
    Returns [(id, name, day, hour), ...] for every class row.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, day, hour FROM classes ORDER BY name, day, hour")
    rows = cur.fetchall()
    conn.close()
    return rows

