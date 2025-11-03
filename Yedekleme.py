import shutil, datetime
from pathlib import Path
from database import get_db_path, get_storage_root

def backup_database():
    db_path = Path(get_db_path())
    backup_dir = get_storage_root() / "yedek_database"
    backup_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    backup_path = backup_dir / f"dance_school{date_str}.db"

    shutil.copy(str(db_path), str(backup_path))
    print(f"✅ Database buraya yedeklendi: {backup_path}")

if __name__ == "__main__":
    backup_database()
