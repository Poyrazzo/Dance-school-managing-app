import sys
from PyQt5.QtWidgets import QApplication
from database import init_db, update_left_classes_for_all_students
from ui.main_window import MainWindow  # Adjust the import path!

def main():
    # Initialize DB
    init_db()
    update_left_classes_for_all_students()  # Update left classes on startup
    

    # Create app and show main window
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
