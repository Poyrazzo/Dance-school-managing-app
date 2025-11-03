from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QTabWidget, QSpacerItem, QSizePolicy, QDateEdit,QLineEdit,QMessageBox,QDialog, QLabel,QHBoxLayout,QTableWidget, QTableWidgetItem
)
from PyQt5.QtGui import QIcon
from class_management import ClassManager
from student_management import StudentManager
from functools import partial
from datetime import datetime,timedelta  # 🟢 Import once at the top!
from hesap_dialog import HesapDialog
import pandas as pd
import os
from database import get_class_id
from PyQt5.QtCore import QTimer, QTime, QDateTime,Qt
import subprocess
from PyQt5.QtWidgets import QAction
from PyQt5.QtGui import QKeySequence
import re
from pathlib import Path
from database import get_db_path,get_storage_root
from utils import tr_norm

PROJECT_ROOT = Path(__file__).resolve().parent  # this file's folder


        # 🔥 Style for better visibility
button_style = """
            QPushButton {
                font-weight: bold;
                font-size: 20px;
                padding: 6px 12px;
                border: 2px solid #000;
                border-radius: 6px;
                background-color: #f0f0f0;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
        """

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        
        # UI setup...
        self.setWindowTitle("111 Dans okulu")
        self.setWindowIcon(QIcon("resources/111.png"))
        self.resize(900, 600)
        self.showMaximized()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        # Class tabs (must exist before manager classes)
        self.class_tabs = QTabWidget()
        tabbar = self.class_tabs.tabBar()
        tabbar.setMovable(True)
        tabbar.setUsesScrollButtons(True)
        tabbar.tabMoved.connect(self._persist_class_tab_order)

        # apply to the *bar*, not the widget
        tabbar.setStyleSheet("""
            QTabBar::tab {
                min-height: 30px;           /* enforce taller tabs */
                padding: 12px 20px;         /* extra top/bottom space */
                font-size: 20px;
                font-weight: 600;
            }
            QTabBar::tab:selected { 
                background: #e8f0ff;
            }
        """)

        self.class_tabs.setElideMode(Qt.ElideRight)  # long labels get ellipsis nicely
        self.layout.addWidget(self.class_tabs)


        # Managers - must be created AFTER widgets are defined
        self.class_manager = ClassManager(self)
        self.student_manager = StudentManager(self)

        # Top button layout...
        self.setup_buttons()

        # Load classes on startup
        self.class_manager.load_classes()
        self.class_tabs.currentChanged.connect(self.class_manager.load_class_times)

        save_button = QPushButton("💾 Sınıf başına Excel kaydet")
        save_button.setStyleSheet("font-weight: bold; font-size: 14px; background-color: #cce5ff;")
        save_button.clicked.connect(self.save_each_class_to_separate_excels)
        self.button_layout.addWidget(save_button)

        
        self.backup_button = QPushButton("💾 Yedekle")
        self.backup_button.setStyleSheet("font-weight: bold; font-size: 14px; background-color: #cce5ff;")
        self.backup_button.clicked.connect(self.backup_database)
        self.button_layout.addWidget(self.backup_button)
        self.setup_auto_save_timer()

    def _persist_class_tab_order(self, from_index, to_index):
                # Save order whenever the user drags a tab
                from database import normalize_class_key, save_class_tab_order
                names = [self.class_tabs.tabText(i) for i in range(self.class_tabs.count())]
                order_keys = [normalize_class_key(n) for n in names]
                save_class_tab_order(order_keys)


    def setup_buttons(self):


        # 🔥 Top layout
        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()
        self.button_widget.setLayout(self.button_layout)
        self.layout.insertWidget(0, self.button_widget)

        # 🔥 Buttons on the left
        self.add_class_button = QPushButton("Sınıf Ekle")
        self.add_class_button.setStyleSheet(button_style)
        self.add_class_button.clicked.connect(self.class_manager.add_class_dialog)
        self.button_layout.addWidget(self.add_class_button)

        self.edit_class_button = QPushButton("Sınıf bilgisini düzenle")
        self.edit_class_button.setStyleSheet(button_style)
        self.edit_class_button.clicked.connect(self.class_manager.edit_current_class_instance)
        self.button_layout.addWidget(self.edit_class_button)

        self.delete_class_button = QPushButton("Sınıfı sil")
        self.delete_class_button.setStyleSheet(button_style)
        self.delete_class_button.clicked.connect(self.class_manager.delete_current_class_instance)
        self.button_layout.addWidget(self.delete_class_button)

        # 🔥 Spacer for centering the search bar
        self.button_layout.addStretch()

        # 🔥 Centered search bar and search buttons
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("İsim veya numara ile ara...")
        self.search_bar.setFixedWidth(350)
        self.search_bar.setFixedHeight(45) 
        self.search_bar.returnPressed.connect(self.search_globally)  # 🚀 Enter triggers global search
        self.button_layout.addWidget(self.search_bar)

        self.search_button_current = QPushButton("🔍 Bu sınıfta")
        self.search_button_current.setStyleSheet(button_style)
        self.search_button_current.clicked.connect(self.search_in_current_tab)
        self.button_layout.addWidget(self.search_button_current)

        self.search_button_all = QPushButton("🔎 Hepsinde")
        self.search_button_all.setStyleSheet(button_style)
        self.search_button_all.clicked.connect(self.search_globally)
        self.button_layout.addWidget(self.search_button_all)

        self.send_messages_button = QPushButton("📨 WP Mesaj yolla")
        self.send_messages_button.setStyleSheet(button_style)
        self.send_messages_button.clicked.connect(self.notify_students_with_zero_kalan_gun)
        self.button_layout.addWidget(self.send_messages_button)

        # 🔥 Spacer for centering
        self.button_layout.addStretch()

        # 🔥 Buttons on the right
        self.refresh_button = QPushButton()
        self.refresh_button.setIcon(QIcon.fromTheme("view-refresh"))
        self.refresh_button.setToolTip("Refresh Left Courses")
        self.refresh_button.setFixedSize(32, 32)
        self.refresh_button.clicked.connect(self.class_manager.refresh_left_courses)
        self.button_layout.addWidget(self.refresh_button)

        # Geri Al button (top-right, next to refresh)
        self.undo_button = QPushButton()
        self.undo_button.setIcon(QIcon.fromTheme("edit-undo"))
        self.undo_button.setToolTip("Geri Al (Ctrl+Z)")
        self.undo_button.setFixedSize(32, 32)
        self.undo_button.clicked.connect(self.student_manager.undo_last_action)
        self.undo_button.setEnabled(False)  # starts disabled; we’ll toggle it
        self.button_layout.addWidget(self.undo_button)


        self.hesap_button = QPushButton("Hesap")
        self.hesap_button.setStyleSheet(button_style)
        self.hesap_button.clicked.connect(self.open_hesap_dialog)
        self.button_layout.addWidget(self.hesap_button)


    def open_hesap_dialog(self):
        self.hesap_dialog = HesapDialog(self)
        self.hesap_dialog.show()

    def get_current_class_id(self):
        current_tab_index = self.class_tabs.currentIndex()
        if current_tab_index == -1:
            return None

        class_name = self.class_tabs.tabText(current_tab_index)
        day_hour_tabs = self.class_tabs.widget(current_tab_index).layout().itemAt(0).widget()

        data = day_hour_tabs.tabBar().tabData(day_hour_tabs.currentIndex())  # ✅
        if not data:
            return None
        day, hour = data

        from database import get_class_id
        return get_class_id(class_name, day, hour)


    def create_date_edit(self, date_str, class_id, table_widget, row, col):
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("dd-MM-yyyy")
        if date_str:
            try:
                date_edit.setDate(datetime.strptime(date_str, "%Y-%m-%d"))
            except:
                date_edit.setDate(datetime.today())
        else:
            date_edit.setDate(datetime.today())
        date_edit.dateChanged.connect(
            partial(self.student_manager.update_student_date_from_calendar, class_id, table_widget, row, col)
        )
        return date_edit

    def add_student_dialog(self, class_id, table_widget):
        self.student_manager.add_student_dialog(class_id, table_widget)

    def edit_selected_student_direct(self, student_id, class_id, table_widget):
        self.student_manager.edit_selected_student_direct(student_id, class_id, table_widget)

    def delete_selected_student_direct(self, student_id, class_id, table_widget):
        self.student_manager.delete_selected_student_direct(student_id, class_id, table_widget)

    def extend_student_courses(self, student_id, class_id, table_widget):
        self.student_manager.extend_student_courses(student_id, class_id, table_widget)

    def update_student_from_table(self, class_id, table_widget, item):
        self.student_manager.update_student_from_table(class_id, table_widget, item)

    def refresh_current_tab_preserve_position(self):
        # Save the currently selected class tab index
        class_tab_index = self.class_tabs.currentIndex()

        # Save the currently selected day/hour tab index (if any)
        day_hour_index = -1
        if class_tab_index != -1:
            current_class_widget = self.class_tabs.widget(class_tab_index)
            if current_class_widget:
                day_hour_tabs = current_class_widget.layout().itemAt(0).widget()
                if isinstance(day_hour_tabs, QTabWidget):
                    day_hour_index = day_hour_tabs.currentIndex()

        # 🔥 Perform the refresh
        self.class_manager.refresh_left_courses()

        # 🔥 Restore the class tab
        if class_tab_index != -1:
            self.class_tabs.setCurrentIndex(class_tab_index)

            # 🔥 After restoring the class tab, also restore the day/hour tab
            current_class_widget = self.class_tabs.widget(class_tab_index)
            if current_class_widget:
                day_hour_tabs = current_class_widget.layout().itemAt(0).widget()
                if isinstance(day_hour_tabs, QTabWidget) and day_hour_index != -1:
                    # ⚡️ Restore the previously selected day/hour tab
                    day_hour_tabs.setCurrentIndex(day_hour_index)



    def save_all_classes_to_excel(self):
        from database import get_unique_class_names, get_class_times_by_name, get_class_id, get_students_by_class_id
        import pandas as pd, os
        from datetime import datetime
        from PyQt5.QtWidgets import QMessageBox

        # --- where to save ---
        base_path = get_storage_root() / "Dersler"
        base_path.mkdir(parents=True, exist_ok=True)

        today_str = datetime.today().strftime("%d-%m-%Y")
        file_path = base_path / f"{today_str}.xlsx"
        n = 1
        while file_path.exists():
            file_path = base_path / f"{today_str} ({n}).xlsx"
            n += 1

        writer = pd.ExcelWriter(str(file_path), engine="xlsxwriter")


        wb = writer.book
        # Force Excel to recalc formulas on open (supports old & new XlsxWriter)
        if hasattr(wb, "set_calc_on_load"):
            wb.set_calc_on_load()   # newer XlsxWriter
        else:
            wb.calc_on_load = True  # older XlsxWriter: it's a boolean attribute



        # ---- formats ----
        header_fmt = wb.add_format({
            "bold": True, "font_color": "white", "align": "center",
            "valign": "vcenter", "bg_color": "#1f4e79", "border": 1
        })
        center_y = wb.add_format({"align": "center", "valign": "vcenter", "border": 1, "bg_color": "#ffe699"})
        phone_y  = wb.add_format({"align": "center", "valign": "vcenter", "border": 1, "bg_color": "#ffe699"})
        # Use Turkish-looking format with dashes
        date_y   = wb.add_format({"num_format": "dd-mm-yyyy", "align": "center", "valign": "vcenter", "border": 1, "bg_color": "#ffe699"})
        blue_col_fmt = wb.add_format({"bg_color": "#1f4e79", "font_color": "white", "align": "center", "valign": "vcenter", "border": 1})
        blue_center = wb.add_format({
            "bg_color": "#1f4e79", "font_color": "white",
            "align": "center", "valign": "vcenter", "border": 1
        })
        blue_date = wb.add_format({
            "bg_color": "#1f4e79", "font_color": "white",
            "align": "center", "valign": "vcenter", "border": 1,
            "num_format": "dd-mm-yyyy"
        })
        date_mdy = wb.add_format({
            "num_format": "mm/dd/yyyy",
            "align": "center", "valign": "vcenter",
            "border": 1, "bg_color": "#ffe699"
        })
                        
        # conditional colors for KALAN GÜN (F)
        kalan_green = {"type": "cell", "criteria": ">=", "value": 0, "format": wb.add_format({"bg_color": "#c6efce", "border": 1})}
        kalan_pink  = {"type": "cell", "criteria": "<",  "value": 0, "format": wb.add_format({"bg_color": "#f8cbad", "border": 1})}

        # columns: A NUMARA, B ADI SOYADI, C TELEFON, D BAŞLANGIÇ, E ÖDEME, F KALAN GÜN, G <TODAY>
        col_widths = [9, 30, 20, 18, 18, 12, 16]  # a bit wider for phone/dates

        has_data = False
        today_excel_text = datetime.today().strftime("%m/%d/%Y")



        for class_name in get_unique_class_names():
            for day, hour in get_class_times_by_name(class_name):
                class_id = get_class_id(class_name, day, hour)
                students = get_students_by_class_id(class_id)
                if not students:
                    continue
                has_data = True

                # build rows
                rows = []
                end_dates = []  # <-- add this before the loop

                for i, s in enumerate(students, start=1):
                    end_dates.append(s[4] or "")  # s[4] = ÖDEME TARİHİ from DB
                    rows.append({
                        "NUMARA": i,
                        "ADI SOYADI": s[1] or "",
                        "TELEFON": s[2] or "",
                        "BAŞLANGIÇ TARİHİ": "",   # we'll compute from end date
                        "ÖDEME TARİHİ": "",        # will be the formula (D + 28)
                        "KALAN GÜN": "",
                        "": ""
                    })
                df = pd.DataFrame(rows, columns=["NUMARA","ADI SOYADI","TELEFON","BAŞLANGIÇ TARİHİ","ÖDEME TARİHİ","KALAN GÜN",""])

                sheet = f"{class_name}_{day}_{hour}".replace(":", "-")
                df.to_excel(writer, sheet_name=sheet, index=False)
                ws = writer.sheets[sheet]

                # set widths
                for col, width in enumerate(col_widths):
                    ws.set_column(col, col, width)
                ws.set_row(0, 20)  # no global style

                # re-write A1..F1 in blue, G1 stays normal (yellow date cell)
                headers = ["NUMARA","ADI SOYADI","TELEFON","BAŞLANGIÇ TARİHİ","ÖDEME TARİHİ","KALAN GÜN"]
                for c in range(6):  # A..F
                    ws.write(0, c, headers[c], header_fmt)

                ws.write(0, 6, "BUGÜN", center_y)          # G1 title (not blue)
                ws.write_formula(1, 6, "=TODAY()", date_y)   # G2 holds TODAY(); we'll point all rows to $G$2



                # write body with formulas
                for r in range(len(df)):
                    excel_row = r + 1
                    rownum    = excel_row + 1

                    # A..C
                    ws.write(excel_row, 0, df.iloc[r, 0], center_y)  # NUMARA
                    ws.write(excel_row, 1, df.iloc[r, 1], center_y)  # ADI SOYADI
                    ws.write(excel_row, 2, df.iloc[r, 2], phone_y)   # TELEFON

                    # Compute D from ÖDEME TARİHİ in DB: start = end - 28 days (write as REAL date)
                    raw_end = students[r][4]  # DB 'end_time' / ÖDEME TARİHİ for this student
                    end_dt  = self._parse_end_date(raw_end)
                    if end_dt is not None:
                        start_dt = end_dt - timedelta(days=28)
                        ws.write_datetime(excel_row, 3, start_dt, date_mdy)  # REAL date
                    else:
                        ws.write_blank(excel_row, 3, None, date_mdy)         # blank cell, not a text ""


                    # E (ÖDEME TARİHİ) = SUM(D{row}+28)  — no IF guard, use real date format
                    ws.write_formula(excel_row, 4, f'=SUM(D{rownum}+28)', date_mdy)

                    # F (KALAN GÜN) = E{row} - $G$2  (remaining days)
                    ws.write_formula(excel_row, 5, f'=IF(E{rownum}="","",E{rownum}-$G$2)', center_y)




                # conditional formatting for F
                last_row = len(df) + 1
                ws.conditional_format(f"F2:F{last_row}", kalan_green)
                ws.conditional_format(f"F2:F{last_row}", kalan_pink)

                # freeze header
                ws.freeze_panes(1, 0)

        writer.close()

        if has_data:
            QMessageBox.information(self, "Export Complete", f"Kaydedildi:\n{file_path}")
        else:
            QMessageBox.information(self, "No Data", "Kaydedilecek veri bulunamadı.")



    def setup_auto_save_timer(self):
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self.check_and_save_data)
        self.auto_save_timer.start(60000)  # Check every minute

    def check_and_save_data(self):
        current_time = QTime.currentTime()
        if current_time.hour() == 22 and current_time.minute() == 30:
            # 🔥 Save in main window
            self.save_all_classes_to_excel()

            # 🔥 Also save in Kasa if open
            if hasattr(self, 'hesap_dialog') and self.hesap_dialog.isVisible():
                self.hesap_dialog.save_to_excel()
                self.hesap_dialog.save_as_png()


    def notify_students_with_zero_kalan_gun(self):
        subprocess.Popen(["python", "send_whatsapp.py"])
        print("[INFO] Launched WhatsApp messaging script in a separate process.")

    def filter_students_in_current_tab(self, search_text):
        key = tr_norm(search_text)
        if not key:
            self.refresh_current_tab_preserve_position()
            return

        class_tab_index = self.class_tabs.currentIndex()  # ← self.class_tabs
        if class_tab_index == -1:
            return

        current_class_widget = self.class_tabs.widget(class_tab_index)  # ← self.class_tabs
        day_hour_tabs = current_class_widget.layout().itemAt(0).widget()
        student_table = day_hour_tabs.currentWidget().layout().itemAt(0).widget()

        for row in range(student_table.rowCount()):
            name_item = student_table.item(row, 0)
            number_item = student_table.item(row, 1)
            if not name_item or not number_item:
                student_table.setRowHidden(row, True)
                continue

            name_key   = tr_norm(name_item.text())
            number_key = number_item.text().replace(" ", "")
            student_table.setRowHidden(row, not (key in name_key or key in number_key))



    def search_in_current_tab(self):
        from utils import tr_norm
        from PyQt5.QtWidgets import QMessageBox

        raw = (self.search_bar.text() or "").strip()   # ← search_bar
        if not raw:
            QMessageBox.information(self, "Bilgi", "Arama kutusu boş.")
            return

        norm_q = tr_norm(raw)
        digits_q = "".join(ch for ch in raw if ch.isdigit())

        idx = self.class_tabs.currentIndex()
        if idx < 0:
            QMessageBox.information(self, "Bilgi", "Önce bir sınıf sekmesi seçin.")
            return

        current_widget = self.class_tabs.widget(idx)
        if not current_widget or not current_widget.layout() or current_widget.layout().count() == 0:
            QMessageBox.information(self, "Bilgi", "Bu sekmede tablo bulunamadı.")
            return

        day_hour_tabs = current_widget.layout().itemAt(0).widget()
        if day_hour_tabs is None:
            QMessageBox.information(self, "Bilgi", "Alt sekmeler bulunamadı.")
            return

        table = day_hour_tabs.currentWidget().layout().itemAt(0).widget()
        if table is None:
            QMessageBox.information(self, "Bilgi", "Tablo bulunamadı.")
            return

        # columns: 0=İsim, 1=Numara
        for r in range(table.rowCount()):
            name_item = table.item(r, 0)
            phone_item = table.item(r, 1)

            name_txt = name_item.text() if name_item else ""
            phone_txt = (phone_item.text() if phone_item else "").replace(" ", "")

            if (norm_q and tr_norm(name_txt).find(norm_q) != -1) or (digits_q and phone_txt.find(digits_q) != -1):
                table.selectRow(r)
                if name_item:
                    table.scrollToItem(name_item)
                return

        QMessageBox.information(self, "Sonuç", "Bu alt sekmede eşleşen öğrenci bulunamadı.")


    def search_globally(self):
        from PyQt5.QtWidgets import QMessageBox
        from database import search_students_by_name_or_number
        from utils import tr_norm

        raw = (self.search_bar.text() or "").strip()

        # En az bir harf veya rakam (normalize sonrası)
        if not tr_norm(raw) and not any(ch.isdigit() for ch in raw):
            QMessageBox.information(self, "Bilgi", "En az bir harf veya rakam girin.")
            return

        # --- 1) Normal sorgu
        rows_main = search_students_by_name_or_number(raw)

        # --- 2) İ/ı varyantını dene → İ=I, ı=i eşitliği garantisi
        def flip_i_variants(s: str) -> str:
            trans = str.maketrans({
                "i": "ı", "ı": "i",
                "I": "İ", "İ": "I",
            })
            return s.translate(trans)

        rows_alt = []
        alt = flip_i_variants(raw)
        if alt != raw:
            rows_alt = search_students_by_name_or_number(alt)

        # --- 3) Birleştir (id bazlı tekilleme, sırayı koru)
        merged = []
        seen = set()
        for lst in (rows_main, rows_alt):
            for row in lst:  # (sid, sname, phone, cname, day, hour)
                sid = row[0]
                if sid not in seen:
                    seen.add(sid)
                    merged.append(row)

        # --- 4) Sonuca göre
        if not merged:
            QMessageBox.information(self, "Sonuç", "Eşleşen öğrenci bulunamadı.")
            return

        if len(merged) == 1:
            sid, sname, phone, cname, day, hour = merged[0]
            self.goto_student(sid, cname, day, hour)
            return

        # Birden fazla sonuç → TEK KULLANIMLIK POPUP (eski davranış)
        self._show_search_results_popup(merged)



    def goto_student(self, student_id, class_name, day, hour):
        # 1) Switch to the correct CLASS tab
        target_idx = None
        for i in range(self.class_tabs.count()):
            if self.class_tabs.tabText(i).strip().lower() == class_name.strip().lower():
                target_idx = i
                break
        if target_idx is None:
            QMessageBox.warning(self, "Bulunamadı", f"Sınıf bulunamadı: {class_name}")
            return

        # Switch & force build of sub-tabs
        self.class_tabs.setCurrentIndex(target_idx)
        # make sure the sub-tabs are present now
        self.class_manager.load_class_times()

        # 2) Find the right DAY/HOUR sub-tab by its tabData (day, hour)
        current_class_widget = self.class_tabs.widget(target_idx)
        day_hour_tabs = current_class_widget.layout().itemAt(0).widget()

        # Normalize for robust match
        want_day  = (day or "").strip()
        want_hour = (hour or "").strip()

        found_sub = False
        for i in range(day_hour_tabs.count()):
            data = day_hour_tabs.tabBar().tabData(i)
            if not data:
                continue
            d_str, h_str = data
            if (d_str or "").strip() == want_day and (h_str or "").strip() == want_hour:
                day_hour_tabs.setCurrentIndex(i)
                found_sub = True
                break

        if not found_sub:
            # Fallback: try to match by text if tabData not found (older tabs)
            combo_txt = f"{want_day} {want_hour}"
            for i in range(day_hour_tabs.count()):
                if combo_txt in day_hour_tabs.tabText(i):
                    day_hour_tabs.setCurrentIndex(i)
                    found_sub = True
                    break

        if not found_sub:
            QMessageBox.warning(self, "Bulunamadı", f"Sekme bulunamadı: {want_day} {want_hour}")
            return

        # 3) Select the student row in the current table
        student_table = day_hour_tabs.currentWidget().layout().itemAt(0).widget()
        for row in range(student_table.rowCount()):
            id_item = student_table.item(row, 8)  # hidden ID column
            if id_item and id_item.text().isdigit() and int(id_item.text()) == student_id:
                student_table.selectRow(row)
                student_table.scrollToItem(id_item)
                return

        QMessageBox.information(self, "Öğrenci", "Öğrenci satırı bulunamadı (muhtemelen tablo henüz yüklenmedi).")


    def backup_database(self):
        import shutil, datetime
        from PyQt5.QtWidgets import QMessageBox

        db_path = Path(get_db_path())
        backup_dir = get_storage_root() / "yedek_database"
        backup_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        backup_path = backup_dir / f"dance_school{date_str}.db"

        try:
            shutil.copy(str(db_path), str(backup_path))
            QMessageBox.information(self, "Yedekleme Başarılı",
                                    f"Veritabanı yedeği oluşturuldu:\n{backup_path}")
        except Exception as e:
            QMessageBox.warning(self, "Yedekleme Hatası",
                                f"Yedekleme sırasında bir hata oluştu:\n{e}")


    def update_undo_button_state(self, has_undo: bool):
        try:
            self.undo_button.setEnabled(bool(has_undo))
        except Exception:
            pass

    def _parse_end_date(self, s):
        if not s:
            return None
        txt = str(s).strip()
        try:
            from datetime import datetime as _dt

            # 1) ISO: 2025-10-01 or 2025/10/01 or 2025.10.01  -> year-first
            if re.fullmatch(r"\d{4}[-/.]\d{2}[-/.]\d{2}", txt):
                t = txt.replace("/", "-").replace(".", "-")
                return _dt.strptime(t, "%Y-%m-%d")

            # 2) Day-first: 01-10-2025, 01/10/2025, 01.10.2025  -> Turkish style
            if re.fullmatch(r"\d{2}[-/.]\d{2}[-/.]\d{4}", txt):
                t = txt.replace("/", "-").replace(".", "-")
                return _dt.strptime(t, "%d-%m-%Y")

            # 3) Fallback: let pandas try day-first (no warning because ISO already handled)
            import pandas as pd
            dt = pd.to_datetime(txt, errors="coerce", dayfirst=True)
            if pd.isna(dt):
                return None
            return dt.to_pydatetime()
        except Exception:
            return None

    def save_each_class_to_separate_excels(self):
        """
        Creates one Excel file per CLASS (HipHop.xlsx, Bachata.xlsx, …).
        Each file contains tabs for its sub-classes (e.g., "Cmrtsi 12.00 - Pazar 12.00"),
        with the same formatting + formulas you already use.
        """
        from database import (
            get_unique_class_names, get_class_times_by_name, get_class_id, get_students_by_class_id
        )
        import pandas as pd, re
        from datetime import datetime, timedelta
        from PyQt5.QtWidgets import QMessageBox

        base_path = get_storage_root() / "Dersler"
        base_path.mkdir(parents=True, exist_ok=True)
        today_str = datetime.today().strftime("%d-%m-%Y")

        total_files = 0
        total_sheets = 0
        total_rows = 0

        # ----- iterate top-level classes -----
        for class_name in get_unique_class_names():
            times = get_class_times_by_name(class_name)
            if not times:
                continue

            # file name: <DATE> - <ClassName>.xlsx  (unique if already exists)
            safe_name = re.sub(r'[^\w\s\-\u00C0-\u024F]', "_", class_name).strip()
            file_path = base_path / f"{today_str} - {safe_name}.xlsx"
            n = 1
            while file_path.exists():
                file_path = base_path / f"{today_str} - {safe_name} ({n}).xlsx"
                n += 1

            writer = pd.ExcelWriter(str(file_path), engine="xlsxwriter")
            wb = writer.book
            if hasattr(wb, "set_calc_on_load"):
                wb.set_calc_on_load()
            else:
                wb.calc_on_load = True

            # formats (same palette as before)
            header_fmt = wb.add_format({
                "bold": True, "font_color": "white", "align": "center",
                "valign": "vcenter", "bg_color": "#1f4e79", "border": 1
            })
            center_y = wb.add_format({"align": "center", "valign": "vcenter", "border": 1, "bg_color": "#ffe699"})
            phone_y  = wb.add_format({"align": "center", "valign": "vcenter", "border": 1, "bg_color": "#ffe699"})
            date_y   = wb.add_format({"num_format": "dd-mm-yyyy", "align": "center", "valign": "vcenter", "border": 1, "bg_color": "#ffe699"})
            blue_center = wb.add_format({"bg_color": "#1f4e79", "font_color": "white", "align": "center", "valign": "vcenter", "border": 1})
            date_mdy = wb.add_format({"num_format": "mm/dd/yyyy", "align": "center", "valign": "vcenter", "border": 1, "bg_color": "#ffe699"})
            kalan_green = {"type": "cell", "criteria": ">=", "value": 0, "format": wb.add_format({"bg_color": "#c6efce", "border": 1})}
            kalan_pink  = {"type": "cell", "criteria": "<",  "value": 0, "format": wb.add_format({"bg_color": "#f8cbad", "border": 1})}
            col_widths = [9, 30, 20, 18, 18, 12, 16]

            class_has_data = False

            # ----- each sub-class becomes a sheet -----
            for (day, hour) in times:
                class_id = get_class_id(class_name, day, hour)
                students = get_students_by_class_id(class_id)
                if not students:
                    continue

                class_has_data = True
                total_sheets += 1

                # build rows
                rows = []
                for i, s in enumerate(students, start=1):
                    rows.append({
                        "NUMARA": i,
                        "ADI SOYADI": s[1] or "",
                        "TELEFON": s[2] or "",
                        "BAŞLANGIÇ TARİHİ": "",   # computed from end date (28 days before)
                        "ÖDEME TARİHİ": "",        # formula (D + 28)
                        "KALAN GÜN": "",
                        "": ""
                    })
                df = pd.DataFrame(rows, columns=["NUMARA", "ADI SOYADI", "TELEFON", "BAŞLANGIÇ TARİHİ", "ÖDEME TARİHİ", "KALAN GÜN", ""])

                sheet = f"{day} {hour}".replace(":", "-")
                df.to_excel(writer, sheet_name=sheet, index=False)
                ws = writer.sheets[sheet]

                # widths and header styling
                for col, width in enumerate(col_widths):
                    ws.set_column(col, col, width)
                ws.set_row(0, 20)

                headers = ["NUMARA","ADI SOYADI","TELEFON","BAŞLANGIÇ TARİHİ","ÖDEME TARİHİ","KALAN GÜN"]
                for c in range(6):
                    ws.write(0, c, headers[c], header_fmt)

                ws.write(0, 6, "BUGÜN", center_y)
                ws.write_formula(1, 6, "=TODAY()", date_y)  # G2

                # body with formulas
                for r in range(len(df)):
                    excel_row = r + 1
                    rownum    = excel_row + 1

                    # A..C
                    ws.write(excel_row, 0, df.iloc[r, 0], center_y)  # NUMARA
                    ws.write(excel_row, 1, df.iloc[r, 1], center_y)  # ADI
                    ws.write(excel_row, 2, df.iloc[r, 2], phone_y)   # TEL

                    # D = start = (end_from_db - 28) as REAL date (if end present)
                    raw_end = students[r][4]
                    end_dt  = self._parse_end_date(raw_end)
                    if end_dt is not None:
                        start_dt = end_dt - timedelta(days=28)
                        ws.write_datetime(excel_row, 3, start_dt, date_mdy)
                    else:
                        ws.write_blank(excel_row, 3, None, date_mdy)

                    # E = D + 28
                    ws.write_formula(excel_row, 4, f'=IF(D{rownum}="", "", D{rownum}+28)', date_mdy)
                    # F = E - $G$2
                    ws.write_formula(excel_row, 5, f'=IF(E{rownum}="","",E{rownum}-$G$2)', center_y)

                last_row = len(df) + 1
                ws.conditional_format(f"F2:F{last_row}", kalan_green)
                ws.conditional_format(f"F2:F{last_row}", kalan_pink)
                ws.freeze_panes(1, 0)

                total_rows += len(students)

            writer.close()
            if class_has_data:
                total_files += 1
            else:
                # remove empty file (no students in any sub-class)
                try:
                    import os
                    os.remove(str(file_path))
                except Exception:
                    pass

        if total_files == 0:
            QMessageBox.information(self, "No Data", "Kaydedilecek veri bulunamadı.")
        else:
            QMessageBox.information(
                self, "Tamam",
                f"{total_files} sınıf için Excel oluşturuldu.\n"
                f"Toplam sayfa: {total_sheets}, toplam öğrenci satırı: {total_rows}"
            )

    def _ensure_results_tab(self):
        """
        '🔎 Arama Sonuçları' adında (varsa tekrar kullanacağı) bir sekme yaratır,
        QTableWidget döndürür.
        """
        title = "🔎 Arama Sonuçları"
        # Sekme zaten var mı?
        for i in range(self.class_tabs.count()):
            if self.class_tabs.tabText(i) == title:
                w = self.class_tabs.widget(i)
                tbl = w.findChild(QTableWidget)
                if tbl is not None:
                    return i, tbl
                # yoksa yeni tablo ekle
                container = w
                layout = container.layout() or QVBoxLayout(container)
                if container.layout() is None:
                    container.setLayout(layout)
                tbl = QTableWidget()
                layout.addWidget(tbl)
                return i, tbl

        # Yoksa yeni sekme
        container = QWidget()
        layout = QVBoxLayout(container)
        tbl = QTableWidget()
        layout.addWidget(tbl)
        self.class_tabs.addTab(container, title)
        idx = self.class_tabs.count() - 1
        return idx, tbl


    def _show_search_results_on_tab(self, rows):
        """
        rows: [(sid, sname, phone, cname, day, hour), ...]
        Eski 'sonuç sekmesi' davranışını yeniden uygular.
        """
        idx, table = self._ensure_results_tab()

        # Tablo başlıkları
        headers = ["Adı Soyadı", "Numara", "Sınıf", "Gün", "Saat", "Git"]
        table.clear()
        table.setRowCount(len(rows))
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setDefaultSectionSize(36)

        for r, (sid, sname, phone, cname, day, hour) in enumerate(rows):
            for c, val in enumerate([sname or "", phone or "", cname or "", day or "", hour or ""]):
                it = QTableWidgetItem(str(val))
                it.setTextAlignment(Qt.AlignCenter)
                table.setItem(r, c, it)

            # Git butonu
            btn = QPushButton("Git")
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda _=False, _sid=sid, _cn=cname, _d=day, _h=hour: self.goto_student(_sid, _cn, _d, _h))
            table.setCellWidget(r, 5, btn)

        table.resizeColumnsToContents()
        self.class_tabs.setCurrentIndex(idx)

    def _show_search_results_popup(self, rows):
        """
        rows: [(sid, sname, phone, cname, day, hour), ...]
        Eski davranış: modal POPUP liste, her satırda 'Git' butonu.
        """
        dlg = QDialog(self)
        dlg.setWindowTitle("🔎 Arama Sonuçları")
        dlg.setModal(True)  # modal
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.resize(700, 420)

        lay = QVBoxLayout(dlg)
        table = QTableWidget()
        lay.addWidget(table)

        headers = ["Adı Soyadı", "Numara", "Sınıf", "Gün", "Saat", "Git"]
        table.setColumnCount(len(headers))
        table.setRowCount(len(rows))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(table.SelectRows)
        table.setEditTriggers(table.NoEditTriggers)
        table.verticalHeader().setDefaultSectionSize(36)

        for r, (sid, sname, phone, cname, day, hour) in enumerate(rows):
            # metin hücreleri
            vals = [sname or "", phone or "", cname or "", day or "", hour or ""]
            for c, val in enumerate(vals):
                it = QTableWidgetItem(str(val))
                it.setTextAlignment(Qt.AlignCenter)
                table.setItem(r, c, it)

            # Git butonu (geç bağlanma hatasına karşı argümanları sabitle)
            btn = QPushButton("Git")
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda _=False, _sid=sid, _cn=cname, _d=day, _h=hour: (
                dlg.accept(),  # önce popup'ı kapat
                self.goto_student(_sid, _cn, _d, _h)
            ))
            table.setCellWidget(r, 5, btn)

        # çift tıkla "Git" gibi davran
        def _double_click(row, _col):
            if 0 <= row < len(rows):
                sid, sname, phone, cname, day, hour = rows[row]
                dlg.accept()
                self.goto_student(sid, cname, day, hour)
        table.cellDoubleClicked.connect(_double_click)

        table.resizeColumnsToContents()
        dlg.exec_()  # tek kullanımlık popup
