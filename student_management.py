from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QDateEdit, QDialogButtonBox,
    QTableWidgetItem, QHBoxLayout, QPushButton, QMessageBox, QCheckBox,QWidget,QInputDialog,QTableWidget
)
from PyQt5.QtCore import Qt,QDate
from datetime import datetime, timedelta
from functools import partial
from database import (
    add_student_to_class, get_students_by_class_id, delete_student,
    update_student_info, extend_student_courses_in_db, get_days_of_class,
    update_student_info_full,add_attendance,update_student_left_classes_based_on_single_day,get_attendance_for_student, get_days_of_class,
    get_all_class_instances, add_student_to_class_with_dates,
)
from attendance_calendar import AttendanceCalendar
import pandas as pd
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtGui import QKeySequence,QColor
import pandas as pd
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem
from PyQt5.QtCore import Qt
from datetime import datetime, timedelta
import math

GREEN_ATT = QColor(80, 230, 80)   # more green than before (used for name + KALAN GÜN > 0)
RED_NEG   = QColor(240, 100, 100) # for KALAN GÜN < 0
WHITE_BG  = QColor(255, 255, 255)
BLACK_FG  = QColor(0, 0, 0)
WHITE_FG  = QColor(255, 255, 255)


class StudentManager:
    def __init__(self, main_window):
        

        self.main_window = main_window
        self.TURKISH_DAY_MAP = {
            "Pzt": 0, "Salı": 1, "Çarşamba": 2, "Perşembe": 3,
            "Cuma": 4, "Cmrtsi": 5, "Pazar": 6
        }
        self.undo_stack = []  # list of dicts: {"type": "delete_students", "rows": [...], "class_id": int}

        # Ctrl+Z shortcut
        self.undo_shortcut = QShortcut(QKeySequence.Undo, self.main_window)
        self.undo_shortcut.activated.connect(self.undo_last_action)

        # add after self.TURKISH_DAY_MAP = {...}
        self._DAY_ALIAS = {
            # Monday
            "pzt": 0, "pazartesi": 0, "pztesi": 0, "pzt.": 0,
            # Tuesday
            "salı": 1, "sali": 1,
            # Wednesday
            "çarşamba": 2, "carsamba": 2, "çarsamba": 2, "crs": 2,
            # Thursday
            "perşembe": 3, "persembe": 3, "perş": 3,
            # Friday
            "cuma": 4,
            # Saturday
            "cmrtsi": 5, "cumartesi": 5, "cmt": 5, "cts": 5,
            # Sunday
            "pazar": 6
        }

    def _norm_tr(self, s: str) -> str:
            if not isinstance(s, str):
                return ""
            s = s.strip().lower()
            tr = {"î":"i","â":"a","û":"u","ı":"i","ğ":"g","ş":"s","ç":"c","ö":"o","ü":"u",
                "İ":"i","Ğ":"g","Ş":"s","Ç":"c","Ö":"o","Ü":"u"}
            for k, v in tr.items():
                s = s.replace(k, v)
            return s

    def _day_to_index(self, token: str):
            key = self._norm_tr(token)
            return self._DAY_ALIAS.get(key)


    def add_student_dialog(self, class_id, table_widget):
        day_str = get_days_of_class(class_id)
        days_per_week = len(day_str.split(',')) if day_str else 1
        left_classes = 4 * days_per_week

        dialog = QDialog(self.main_window)
        dialog.setWindowTitle("Add Student")
        
        layout = QFormLayout(dialog)

        name_edit = QLineEdit()
        number_edit = QLineEdit()
        start_date_edit = QDateEdit()
        start_date_edit.setCalendarPopup(True)
        start_date_edit.setDate(QDate.currentDate()) 
        note_edit = QLineEdit()

        layout.addRow("Name:", name_edit)
        layout.addRow("Number:", number_edit)
        layout.addRow("Start Date (YYYY-MM-DD):", start_date_edit)
        layout.addRow("Note:", note_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        excel_btn = QPushButton("Excel'den aktar")
        excel_btn.clicked.connect(
            lambda: self.import_students_from_excel_for_class(dialog, class_id, table_widget)
        )


        layout.addWidget(excel_btn)
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            name = name_edit.text()
            number = number_edit.text()
            number = self.format_phone_number(number) 
            start_date = start_date_edit.date().toString("yyyy-MM-dd")
            note = note_edit.text()
            if name:
                add_student_to_class(class_id, name, number, start_date, note, left_classes)
                self.refresh_student_table(class_id, table_widget)

    def refresh_student_table(self, class_id, table_widget):
        from database import update_student_left_classes, get_students_by_class_id, get_days_of_class

        students = get_students_by_class_id(class_id)
        try:
            table_widget.itemChanged.disconnect()
        except Exception:
            pass

        row_count = max(len(students), 10)
        table_widget.setRowCount(row_count)
        table_widget.verticalHeader().setDefaultSectionSize(40)

        day_str = get_days_of_class(class_id)
        tokens = [t.strip() for t in (day_str or "").split(",") if t.strip()]
        class_days = []
        for t in tokens:
            idx = self._day_to_index(t)
            if idx is not None:
                class_days.append(idx)
        
        today = datetime.today().date()

        # Add column header for "KALAN GÜN"
        headers = ["İsim", "Numara", "Başlangıç Tarihi", "Bitiş Tarihi", "Kalan Ders", "Not", "KALAN GÜN", "Özellikler", "ID"]
        table_widget.setColumnCount(len(headers))
        table_widget.setHorizontalHeaderLabels(headers)

        for row_idx in range(row_count):
            if row_idx < len(students):
                student = students[row_idx]

                try:
                    start_date = datetime.strptime(student[3], "%Y-%m-%d").date()
                except:
                    start_date = today

                try:
                    end_date = datetime.strptime(student[4], "%Y-%m-%d").date()
                except:
                    end_date = today

                # 🔥 Calculate KALAN GÜN
                today = datetime.today().date()
                kalan_gun = (end_date - today).days

                # 🔥 Calculate remaining classes
                remaining = self.count_remaining_classes(today, end_date, class_days)

                # 🔥 Update DB with left_classes
                update_student_left_classes(student[0], remaining)

                # Fill in cells
                for col_idx, value in enumerate(student[1:], start=0):
                    if col_idx in [2, 3]:
                        date_edit = NoScrollDateEdit()
                        date_edit.setCalendarPopup(True)
                        date_edit.setDisplayFormat("dd-MM-yyyy")
                        if value:
                            try:
                                dt = datetime.strptime(value, "%Y-%m-%d").date()
                                date_edit.setDate(QDate(dt.year, dt.month, dt.day))
                            except:
                                date_edit.setDate(QDate.currentDate())
                        else:
                            date_edit.setDate(QDate.currentDate())
                        date_edit.dateChanged.connect(
                            partial(self.update_student_date_from_calendar, class_id, table_widget, row_idx, col_idx)
                        )
                        table_widget.setCellWidget(row_idx, col_idx, date_edit)
                        # 🔔 Highlight name until next class after the latest attendance
                        # ✅ Name highlight until next class after last attendance
                        try:
                            # name column is 0
                            name_item = table_widget.item(row_idx, 0)
                            # get last attendance (if you already have helper use it, else inline)
                            dates = get_attendance_for_student(student[0])  # ["YYYY-MM-DD", ...]
                            last_att = max((datetime.strptime(x, "%Y-%m-%d").date() for x in dates), default=None)

                            if last_att:
                                # compute next class date
                                def _next_class_date(after_date, class_day_indexes):
                                    if not class_day_indexes:
                                        return None
                                    d = after_date + timedelta(days=1)
                                    while True:
                                        if d.weekday() in class_day_indexes:
                                            return d
                                        d += timedelta(days=1)

                                nxt = _next_class_date(last_att, class_days)
                                if nxt and datetime.today().date() < nxt:
                                    name_item.setBackground(GREEN_ATT)  # more green
                                    name_item.setForeground(BLACK_FG)
                                else:
                                    name_item.setBackground(WHITE_BG)
                                    name_item.setForeground(BLACK_FG)
                        except Exception:
                            pass

                    else:
                        item = QTableWidgetItem(str(value) if value else "")
                        item.setTextAlignment(Qt.AlignCenter)
                        table_widget.setItem(row_idx, col_idx, item)

                # Left Classes
                left_item = QTableWidgetItem(str(remaining))
                left_item.setTextAlignment(Qt.AlignCenter)
                table_widget.setItem(row_idx, 4, left_item)

                # KALAN GÜN
                kalan_item = QTableWidgetItem(str(kalan_gun))
                kalan_item.setTextAlignment(Qt.AlignCenter)

                # 🎨 Color rules:
                #  0  → no color (white)
                # >0  → same green as name highlight
                # <0  → red (with white text for contrast)
                if kalan_gun > 0:
                    kalan_item.setBackground(GREEN_ATT)
                    kalan_item.setForeground(BLACK_FG)
                elif kalan_gun < 0:
                    kalan_item.setBackground(RED_NEG)
                    kalan_item.setForeground(WHITE_FG)
                else:
                    kalan_item.setBackground(WHITE_BG)
                    kalan_item.setForeground(BLACK_FG)

                table_widget.setItem(row_idx, 6, kalan_item)


                # Student ID hidden
                student_id_item = QTableWidgetItem(str(student[0]))
                student_id_item.setFlags(student_id_item.flags() & ~Qt.ItemIsEditable)
                table_widget.setItem(row_idx, 8, student_id_item)

                # Buttons
                btn_layout = QHBoxLayout()
                for text, func in [
                    ("Uzat", self.extend_student_courses),
                    ("Sil", self.delete_selected_student_direct)
                ]:
                    btn = QPushButton(text)
                    btn.setFixedSize(50, 25)
                    btn.clicked.connect(partial(func, student[0], class_id, table_widget))
                    btn_layout.addWidget(btn)

                add_btn = QPushButton("+")
                add_btn.setFixedSize(30, 25)
                add_btn.clicked.connect(partial(self.mark_attendance, student[0], class_id, table_widget))
                btn_layout.addWidget(add_btn)

                btn_widget = QWidget()
                btn_widget.setLayout(btn_layout)
                table_widget.setCellWidget(row_idx, 7, btn_widget)


            else:
                for col_idx in range(8):
                    item = QTableWidgetItem("")
                    item.setTextAlignment(Qt.AlignCenter)
                    table_widget.setItem(row_idx, col_idx, item)
                if table_widget.cellWidget(row_idx, 2):
                    table_widget.removeCellWidget(row_idx, 2)
                if table_widget.cellWidget(row_idx, 3):
                    table_widget.removeCellWidget(row_idx, 3)
                table_widget.setCellWidget(row_idx, 7, None)
                dummy_id_item = QTableWidgetItem("-1")
                dummy_id_item.setFlags(dummy_id_item.flags() & ~Qt.ItemIsEditable)
                table_widget.setItem(row_idx, 8, dummy_id_item)
        
        table_widget.setColumnHidden(8, True)
        table_widget.itemChanged.connect(partial(self.update_student_from_table, class_id, table_widget))



    def count_remaining_classes(self, today, end_date, class_days):
        count = 0
        current_date = today
        step = 1 if end_date >= today else -1

        while current_date != end_date:
            if current_date.weekday() in class_days:
                count += step
            current_date += timedelta(days=step)

        return count


    def extend_end_date(self, current_end_date, additional_classes, class_days):
        """
        Extends the student's end date based on class days.
        - If the current end date is not a class day, extend by 2 classes.
        - If it is a class day, extend by 1 class.
        """
        new_end_date = current_end_date

        # Check if current end date is a class day
        if new_end_date.weekday() not in class_days:
            # Not a class day? Extend by 2 classes!
            count = 0
            while count < 2:
                new_end_date += timedelta(days=1)
                if new_end_date.weekday() in class_days:
                    count += 1
        else:
            # Already a class day? Extend by 1 class
            count = 0
            while count < additional_classes:
                new_end_date += timedelta(days=1)
                if new_end_date.weekday() in class_days:
                    count += 1

        return new_end_date




    def extend_student_courses(self, student_id, class_id, table_widget):
        count, ok = QInputDialog.getInt(self.main_window, "Ders sayısını uzat", "Ne kadar ders eklenecek", min=1, max=100)
        if not ok or count <= 0:
            return
        students = get_students_by_class_id(class_id)
        student = next((s for s in students if s[0] == student_id), None)
        if not student:
            return
        try:
            end_date = datetime.strptime(student[4], "%Y-%m-%d").date()
        except:
            end_date = datetime.today().date()
        day_str = get_days_of_class(class_id)
        tokens = [t.strip() for t in (day_str or "").split(",") if t.strip()]
        class_days = []
        for t in tokens:
            idx = self._day_to_index(t)   # uses your alias map (Pazartesi, Pzt, etc.)
            if idx is not None:
                class_days.append(idx)
        new_end_date = self.extend_end_date(end_date, count, class_days)
        extend_student_courses_in_db(student_id, count, new_end_date.strftime("%Y-%m-%d"))
        self.refresh_student_table(class_id, table_widget)



    def edit_selected_student_direct(self, student_id, class_id, table_widget):
        dialog = QDialog(self.main_window)
        dialog.setWindowTitle("Seçili öğrenciyi Düzenle")
        layout = QFormLayout(dialog)

        # 🟢 Corrected: Use column 8 for the ID, and skip empty/None rows safely
        row_idx = next((i for i in range(table_widget.rowCount())
                        if table_widget.item(i, 8) and table_widget.item(i, 8).text().isdigit() and
                        int(table_widget.item(i, 8).text()) == student_id), None)
        if row_idx is None:
            return

        name = table_widget.item(row_idx, 0).text()
        number = table_widget.item(row_idx, 1).text()
        start_date_widget = table_widget.cellWidget(row_idx, 2)
        start_time = start_date_widget.date().toString("yyyy-MM-dd") if start_date_widget else table_widget.item(row_idx, 2).text()
        note = table_widget.item(row_idx, 5).text()

        name_edit = QLineEdit(name)
        number_edit = QLineEdit(number)
        start_date_edit = QDateEdit()
        start_date_edit.setCalendarPopup(True)
        start_date_edit.setDisplayFormat("dd-MM-yyyy")
        try:
            dt = datetime.strptime(start_time, "%Y-%m-%d").date()
            start_date_edit.setDate(QDate(dt.year, dt.month, dt.day))
        except:
            start_date_edit.setDate(QDate.currentDate())
        note_edit = QLineEdit(note)

        layout.addRow("Name:", name_edit)
        layout.addRow("Number:", number_edit)
        layout.addRow("Start Date (DD-MM-YYYY):", start_date_edit)
        layout.addRow("Note:", note_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            new_name = name_edit.text().strip()
            new_number = number_edit.text().strip()
            new_number = self.format_phone_number(new_number)
            new_start_time = start_date_edit.date().toString("yyyy-MM-dd")
            new_note = note_edit.text().strip()
            # 🔥 Only update start_time; end_time stays untouched
            from database import update_student_info
            update_student_info(student_id, new_name, new_number, new_start_time, new_note)
            self.refresh_student_table(class_id, table_widget)


    def update_student_from_table(self, class_id, table_widget, item):
        row = item.row()
        col = item.column()
        if col in (7, 8):  # skip buttons and hidden ID
            return

        # ✅ Safely get previous start/end
        start_item = table_widget.item(row, 2)
        end_item = table_widget.item(row, 3)
        previous_start = start_item.text() if start_item else ""
        previous_end = end_item.text() if end_item else ""

        # Get student ID
        student_id_item = table_widget.item(row, 8)
        if not student_id_item or not student_id_item.text().isdigit():
            return
        student_id = int(student_id_item.text())

        # Get fields
        name = table_widget.item(row, 0).text()
        number = table_widget.item(row, 1).text()
        number = self.format_phone_number(number)  # 🔥 Format the number when editing directly!
        note = table_widget.item(row, 5).text()

        # Update the number in the table visually
        number_item = table_widget.item(row, 1)
        number_item.setText(number)

        # Start & End Dates
        start_date_widget = table_widget.cellWidget(row, 2)
        start_time = start_date_widget.date().toString("yyyy-MM-dd") if start_date_widget else table_widget.item(row, 2).text()
        end_date_widget = table_widget.cellWidget(row, 3)
        end_time = end_date_widget.date().toString("yyyy-MM-dd") if end_date_widget else table_widget.item(row, 3).text()

        # Calculate left_classes
        day_str = get_days_of_class(class_id)
        tokens = [t.strip() for t in (day_str or "").split(",") if t.strip()]
        class_days = []
        for t in tokens:
            idx = self._day_to_index(t)   # uses your alias map (Pazartesi, Pzt, etc.)
            if idx is not None:
                class_days.append(idx)
        today = datetime.today().date()
        end_dt = datetime.strptime(end_time, "%Y-%m-%d").date()
        left_classes = self.count_remaining_classes(today, end_dt, class_days)

        # Update DB
        from database import update_student_info_full
        update_student_info_full(student_id, name, number, start_time, end_time, left_classes, note)

        # Update table cells safely
        table_widget.blockSignals(True)
        # KALAN GÜN
        try:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d").date()
            kalan_gun = (end_dt - start_dt).days
        except:
            kalan_gun = 0

        kalan_item = QTableWidgetItem(str(kalan_gun))
        kalan_item.setTextAlignment(Qt.AlignCenter)
        if kalan_gun > 0:
            kalan_item.setBackground(GREEN_ATT)
            kalan_item.setForeground(BLACK_FG)
        elif kalan_gun < 0:
            kalan_item.setBackground(RED_NEG)
            kalan_item.setForeground(WHITE_FG)
        else:
            kalan_item.setBackground(WHITE_BG)
            kalan_item.setForeground(BLACK_FG)
        table_widget.setItem(row, 6, kalan_item)


        # LEFT CLASSES
        left_item = QTableWidgetItem(str(left_classes))
        left_item.setTextAlignment(Qt.AlignCenter)
        table_widget.setItem(row, 4, left_item)
        table_widget.blockSignals(False)

        try:
            self.refresh_student_table(class_id, table_widget)
        except Exception:
            pass
    


    def update_student_date_from_calendar(self, class_id, table_widget, row, col, qdate):
        date_str = qdate.toString("yyyy-MM-dd")
        
        # 🔥 Directly update table item text
        item = table_widget.item(row, col)
        if item is None:
            item = QTableWidgetItem()
            table_widget.setItem(row, col, item)
        item.setText(date_str)
        item.setTextAlignment(Qt.AlignCenter)

        # 🔥 Directly call the update logic
        self.update_student_from_table(class_id, table_widget, item)

    def delete_selected_student_direct(self, student_id, class_id, table_widget):
        """
        Delete a single student from an active sub-class.
        Before deleting, move to that class group's ESKİLER tab unless a duplicate
        (same name OR phone) already exists there.
        """
        from PyQt5.QtWidgets import QMessageBox
        from database import (
            get_students_by_ids, delete_student, get_class_group_key_by_id,
            ensure_eskiler_class, student_exists_in_class_by_name_or_number,
            move_student_to_class
        )

        # Find the row for this student_id (to read name/number)
        row_idx = next((i for i in range(table_widget.rowCount())
                        if table_widget.item(i, 8)
                        and table_widget.item(i, 8).text().isdigit()
                        and int(table_widget.item(i, 8).text()) == student_id), None)
        if row_idx is None:
            return

        name_item   = table_widget.item(row_idx, 0)
        number_item = table_widget.item(row_idx, 1)
        student_name = (name_item.text() if name_item else "").strip()
        student_num  = (number_item.text() if number_item else "").strip()

        # Confirm
        if QMessageBox.question(
            self.main_window, "Silme Onayı",
            f"'{student_name}' öğrencisini silmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return

        # Snapshot BEFORE we touch DB (for Undo)
        backup_rows = get_students_by_ids([student_id])

        try:
            # Figure out the Eskiler class for THIS group
            name_key, canon_name = get_class_group_key_by_id(class_id)
            esk_class_id = ensure_eskiler_class(canon_name)

            # Duplicate check in Eskiler (same name OR phone)
            if student_exists_in_class_by_name_or_number(esk_class_id, student_name, student_num):
                # Already archived → just delete from active class
                delete_student(student_id)
                info = "öğrenci zaten eskiler de bulunuyordu"
            else:
                # Move (archive) to Eskiler
                move_student_to_class(student_id, esk_class_id)
                info = "öğrenci eskilere eklendi"

            QMessageBox.information(self.main_window, "Tamam", f"{student_name}: {info}")

            # Push undo snapshot
            if backup_rows:
                self.undo_stack.append({
                    "type": "delete_students",
                    "rows": backup_rows,
                    "class_id": class_id,
                    "table_widget": table_widget
                })
                if hasattr(self.main_window, "update_undo_button_state"):
                    self.main_window.update_undo_button_state(bool(self.undo_stack))

            # Refresh
            self.refresh_student_table(class_id, table_widget)

        except Exception as e:
            QMessageBox.warning(self.main_window, "Hata", f"Silinemedi:\n{e}")


    def mark_attendance(self, student_id, class_id, table_widget):
        today_str = datetime.today().strftime("%Y-%m-%d")
        add_attendance(student_id, today_str)
        QMessageBox.information(self.main_window, "Yoklama Kaydedildi", f"Bugünün yoklaması alındı: {today_str}")
        # 🔄 Show the green highlight immediately
        self.refresh_student_table(class_id, table_widget)

    def format_phone_number(self, number):
        # Remove non-digit characters
        digits = ''.join(filter(str.isdigit, number))
        # Format as xxx xxx xx xx
        if len(digits) == 10:  # e.g., 5304567890
            return f"{digits[:3]} {digits[3:6]} {digits[6:8]} {digits[8:10]}"
        return number  # fallback if not 10 digits
    
    def set_student_single_day(self, student_id, class_id, table_widget):
        # Get days of this class
        from database import get_days_of_class
        day_str = get_days_of_class(class_id)
        days_list = [d.strip() for d in day_str.split(",") if d.strip()]

        if not days_list:
            QMessageBox.warning(self.main_window, "Gün Yok", "Bu sınıfın günü bulunamadı.")
            return

        # Show selection dialog
        selected_day, ok = QInputDialog.getItem(
            self.main_window, "Tek Gün Seçimi",
            "Hangi güne göre öğrenci takip edilecek?",
            days_list, 0, False
        )
        if not ok or not selected_day:
            return

        # ✅ Update student's left_classes based only on selected_day
        from database import update_student_left_classes_based_on_single_day
        update_student_left_classes_based_on_single_day(student_id, selected_day)

        # ✅ Refresh table to show updated left_classes
        self.refresh_student_table(class_id, table_widget)



    def delete_selected_students(self, class_id, table_widget):
        """
        Deletes all currently selected rows in the student table.
        Expects student ID in hidden column index 8 (your current layout).
        """
        from PyQt5.QtWidgets import QMessageBox
        from PyQt5.QtCore import Qt
        from database import delete_student, get_students_by_ids

        # 1) Collect selected rows (unique & sorted)
        rows = sorted({idx.row() for idx in table_widget.selectedIndexes()})
        if not rows:
            QMessageBox.information(self.main_window, "Bilgi", "Lütfen tablodan en az bir öğrenci seçin.")
            return

        # 2) Build target list (id, name)
        targets = []
        for r in rows:
            id_item = table_widget.item(r, 8)    # hidden ID column (already set in your table)
            name_item = table_widget.item(r, 0)  # name column
            student_id = None
            if id_item:
                txt = (id_item.text() or "").strip()
                if txt.isdigit():
                    student_id = int(txt)
            if student_id is None:
                continue
            name = name_item.text().strip() if name_item else ""
            targets.append((student_id, name))

        if not targets:
            QMessageBox.warning(self.main_window, "Hata", "Seçili satırlardan öğrenci ID'si okunamadı.")
            return

        # 🔴 IMPORTANT: backup AFTER targets are built
        target_ids = [sid for sid, _ in targets]
        backup_rows = get_students_by_ids(target_ids)  # full rows for undo

        # 3) Confirm
        preview = ", ".join([t[1] for t in targets[:5] if t[1]])
        more = "" if len(targets) <= 5 else f" ve {len(targets) - 5} kişi daha"
        q = f"Seçili {len(targets)} öğrenciyi silmek istediğinize emin misiniz?\n{preview}{more}"
        if QMessageBox.question(self.main_window, "Silme Onayı", q,
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return

        # 4) Move each to ESKİLER instead of hard delete
        from database import move_student_to_eskiler
        moved, fails = 0, 0
        for sid, _ in targets:
            try:
                if move_student_to_eskiler(sid, class_id):
                    moved += 1
                else:
                    fails += 1
            except Exception:
                fails += 1

        # 5) Push undo snapshot (only if we actually had something to backup)
        if backup_rows:
            self.undo_stack.append({
                "type": "delete_students",
                "rows": backup_rows,
                "class_id": class_id,
                "table_widget": table_widget
            })
            if hasattr(self.main_window, "update_undo_button_state"):
                self.main_window.update_undo_button_state(bool(self.undo_stack))


        # 6) Refresh and notify
        try:
            self.refresh_student_table(class_id, table_widget)
        except Exception:
            pass

        msg = [f"ESKİLER'e taşınan: {moved}"]
        if fails:
            msg.append(f"Taşınamayan: {fails}")
        QMessageBox.information(self.main_window, "Sonuç", "\n".join(msg))


    @staticmethod
    def _next_class_date(after_date, class_day_indexes):
        """Return the next date >= (after_date + 1 day) matching any class weekday index."""
        if not class_day_indexes:
            return None
        d = after_date + timedelta(days=1)
        while True:
            if d.weekday() in class_day_indexes:
                return d
            d += timedelta(days=1)
    @staticmethod
    def _last_attendance_date(student_id):
        dates = get_attendance_for_student(student_id)  # ["YYYY-MM-DD", ...]
        if not dates:
            return None
        return max(datetime.strptime(x, "%Y-%m-%d").date() for x in dates)

    def undo_last_action(self):
        """Undo the most recent destructive action (currently: bulk student delete)."""
        from PyQt5.QtWidgets import QMessageBox
        if not self.undo_stack:
            QMessageBox.information(self.main_window, "Geri Al", "Geri alınacak işlem yok.")
            return

        action = self.undo_stack.pop()
        if action.get("type") == "delete_students":
            rows = action.get("rows", [])
            class_id = action.get("class_id")
            try:
                from database import restore_students, update_left_classes_for_all_students
                restore_students(rows)
                try:
                    update_left_classes_for_all_students()
                except Exception:
                    pass
                # refresh UI for that class (if current table passed, use it; else refresh by class)
                table_widget = action.get("table_widget")
                if table_widget is not None:
                    self.refresh_student_table(class_id, table_widget)
                else:
                    # if you keep a mapping from class_id -> table, call that here;
                    # otherwise no-op — the next time user switches tabs it will refresh.
                    pass
                QMessageBox.information(self.main_window, "Geri Al", f"{len(rows)} öğrenci geri yüklendi.")
            except Exception as e:
                QMessageBox.warning(self.main_window, "Geri Al Hatası", f"İşlem geri alınamadı:\n{e}")
        else:
            # future action types
            pass

        if hasattr(self.main_window, "update_undo_button_state"):
            self.main_window.update_undo_button_state(bool(self.undo_stack))

    def import_students_from_excel_for_class(self, parent, class_id, table_widget):
        """
        Choose one or more sheets and import ONLY those rows into the current class.
        Robust header matching (TR/diacritics/whitespace), robust date parsing.
        """
        import math
        import pandas as pd
        from PyQt5.QtWidgets import (
            QFileDialog, QMessageBox, QDialog, QVBoxLayout, QLabel,
            QListWidget, QPushButton, QHBoxLayout, QAbstractItemView
        )
        from datetime import datetime, timedelta
        from database import add_student_to_class_with_dates, update_left_classes_for_all_students

        # --- pick file ---
        path, _ = QFileDialog.getOpenFileName(parent, "Excel seç", "", "Excel (*.xlsx *.xls)")
        if not path:
            return

        try:
            xls = pd.ExcelFile(path)
            sheet_names = xls.sheet_names
        except Exception as e:
            QMessageBox.warning(parent, "Hata", f"Excel açılamadı:\n{e}")
            return
        if not sheet_names:
            QMessageBox.information(parent, "Bilgi", "Bu Excel dosyasında sekme yok.")
            return

        # --- sheet picker ---
        dlg = QDialog(parent); dlg.setWindowTitle("Sekmeleri Seç")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Bu sınıfa eklenecek sekmeleri seçin:"))

        lw = QListWidget()
        lw.setSelectionMode(QAbstractItemView.MultiSelection)
        for s in sheet_names:
            lw.addItem(s)
        v.addWidget(lw)

        row = QHBoxLayout()
        btn_cancel = QPushButton("İptal"); btn_ok = QPushButton("İçe aktar")
        row.addWidget(btn_cancel); row.addStretch(1); row.addWidget(btn_ok)
        v.addLayout(row)
        btn_cancel.clicked.connect(dlg.reject)
        btn_ok.clicked.connect(dlg.accept)

        if dlg.exec_() != QDialog.Accepted:
            return

        selected = [i.text() for i in lw.selectedItems()]
        if not selected:
            QMessageBox.information(parent, "Bilgi", "Hiç sekme seçmediniz.")
            return

        # --- helpers ---
        def _is_blank(x):
            if x is None:
                return True
            try:
                if (isinstance(x, float) and math.isnan(x)) or pd.isna(x):
                    return True
            except Exception:
                pass
            s = str(x).strip()
            return s == "" or s.lower() in ("nan", "nat")

        def _norm(s: str) -> str:
            # lowercase, strip, remove diacritics and non-alphanumerics
            if not isinstance(s, str):
                s = "" if s is None else str(s)
            s = s.strip().lower()
            tr = {
                "ı":"i","ğ":"g","ş":"s","ç":"c","ö":"o","ü":"u",
                "â":"a","î":"i","û":"u",
                "İ":"i","Ğ":"g","Ş":"s","Ç":"c","Ö":"o","Ü":"u"
            }
            for k,v in tr.items(): s = s.replace(k,v)
            import re
            s = re.sub(r"\s+", " ", s)        # collapse spaces
            s = re.sub(r"[\u00a0]", " ", s)  # NBSP -> space
            s = re.sub(r"[^a-z0-9 ]", "", s)
            return s

        def _find_col(df_cols, *cands):
            # build normalized map once
            nmap = {_norm(c): c for c in df_cols}
            wants = [_norm(c) for c in cands]
            # exact
            for w in wants:
                if w in nmap: return nmap[w]
            # substring fallback
            for w in wants:
                for key, orig in nmap.items():
                    if w and w in key:
                        return orig
            return None

        def _parse_date(val):
            """Return a datetime (not date) or None. Tries day-first and month-first and Excel serials."""
            if _is_blank(val):
                return None
            # already a timestamp?
            try:
                if hasattr(val, "to_pydatetime"):
                    return val.to_pydatetime()
            except Exception:
                pass
            # Excel serial number?
            try:
                if isinstance(val, (int, float)) and not math.isnan(val):
                    # pandas handles excel serials if we pass origin='1899-12-30'
                    ts = pd.to_datetime(val, unit="D", origin="1899-12-30", errors="coerce")
                    if not pd.isna(ts):
                        return ts.to_pydatetime()
            except Exception:
                pass
            # string parse
            s = str(val).strip()
            for dayfirst in (True, False):
                ts = pd.to_datetime(s, errors="coerce", dayfirst=dayfirst)
                if not pd.isna(ts):
                    return ts.to_pydatetime()
            return None

        # estimate default left_classes for this class
        try:
            day_str = get_days_of_class(class_id)
            days_per_week = len([d for d in (day_str or "").split(",") if d.strip()]) or 1
        except Exception:
            days_per_week = 1
        default_left = 4 * days_per_week

        total = 0
        errors = []
        period = timedelta(days=28)

        for sname in selected:
            try:
                df = pd.read_excel(path, sheet_name=sname)
            except Exception as e:
                errors.append(f"[{sname}] okunamadı: {e}")
                continue
            if df.empty:
                continue

            name_col  = _find_col(df.columns, "ad soyad", "adi soyadi", "adı soyadı", "isim", "name", "ad")
            phone_col = _find_col(df.columns, "telefon", "telefon no", "gsm", "numara", "phone")
            start_col = _find_col(df.columns, "başlangıç tarihi", "baslangic tarihi", "başlangıç", "baslangic", "start", "start date", "start_time")
            end_col   = _find_col(df.columns, "ödeme tarihi", "odeme tarihi", "bitiş tarihi", "bitis tarihi", "bitiş", "bitis", "end", "end date", "end_time")

            if not name_col:
                errors.append(f"[{sname}] 'Ad/İsim' kolonu bulunamadı.")
                continue

            imported = 0
            for _, row in df.iterrows():
                raw_name = row.get(name_col, "")
                if _is_blank(raw_name):
                    continue
                name  = str(raw_name).strip()
                raw_phone = row.get(phone_col, "") if phone_col else ""
                phone = self.format_phone_number("" if _is_blank(raw_phone) else str(raw_phone))

                sdt = _parse_date(row.get(start_col)) if start_col else None
                edt = _parse_date(row.get(end_col))   if end_col   else None

                if not sdt and edt: sdt = edt - period
                if not edt and sdt: edt = sdt + period
                if not sdt and not edt:
                    sdt = datetime.today()
                    edt = sdt + period

                try:
                    add_student_to_class_with_dates(
                        class_id=class_id,
                        name=name,
                        number=phone,
                        start_date=sdt.strftime("%Y-%m-%d"),
                        end_date=edt.strftime("%Y-%m-%d"),
                        note="",
                        left_classes=default_left
                    )
                    imported += 1
                except Exception as e:
                    errors.append(f"[{sname}] '{name}' eklenemedi: {e}")

            total += imported

        # recalc + refresh UI
        try:
            update_left_classes_for_all_students()
        except Exception:
            pass
        try:
            self.refresh_student_table(class_id, table_widget)
        except Exception:
            pass

        if total and not errors:
            QMessageBox.information(parent, "Tamamlandı", f"Toplam {total} öğrenci içe aktarıldı.")
        elif total and errors:
            QMessageBox.information(parent, "Kısmen tamamlandı",
                f"Toplam {total} öğrenci içe aktarıldı.\n\nHatalar:\n- " + "\n- ".join(errors))
        else:
            QMessageBox.warning(parent, "İçe aktarma başarısız",
                "Hiç öğrenci içe aktarılamadı." + ("\n\nAyrıntılar:\n- " + "\n- ".join(errors) if errors else ""))

from PyQt5.QtWidgets import QDateEdit
from PyQt5.QtCore import Qt

class NoScrollDateEdit(QDateEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.StrongFocus)   # must focus before editing
        self.setCalendarPopup(True)

    def wheelEvent(self, event):
        # Ignore wheel to prevent accidental changes while scrolling the page
        event.ignore()

    def event(self, e):
        # Also block wheel when embedded in parent that forwards wheel events
        if e.type() == e.Wheel:
            return True
        return super().event(e)