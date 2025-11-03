from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QDialog, QFormLayout, QLineEdit,
    QCheckBox, QDialogButtonBox, QMessageBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QHBoxLayout, QPushButton,QSizePolicy,QLabel,QGridLayout,QTimeEdit,
)
from PyQt5.QtCore import Qt,QTime
from datetime import datetime
from functools import partial
from database import (
    get_unique_class_names, get_class_times_by_name, update_class_instance,add_class, class_instance_exists,  get_class_id, ensure_eskiler_class 
)
from PyQt5.QtWidgets import QHeaderView
from attendance_calendar import AttendanceCalendar
from PyQt5.QtWidgets import QAbstractItemView
import sqlite3


class ClassManager:

    DAYS = ["Pzt", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cmrtsi", "Pazar"]


    def __init__(self, main_window):
        self.main_window = main_window
        self.class_tabs = main_window.class_tabs

        # 🌟 Style tabs for better visibility (bold, larger font, clearer selection)
        self.class_tabs.tabBar().setExpanding(True)
        self.class_tabs.setStyleSheet("""
            QTabBar::tab {
                font-weight: bold;
                font-size: 20px; /* Keep this moderate for readability */
                padding: 12px 24px; /* More horizontal & vertical padding */
                min-height: 10px; /* Taller tabs */
                min-width: 200px; /* Wider tabs */
                background: #f0f0f0;
                border: 1px solid #b0b0b0;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #d1e7dd;
                border: 1px solid #0f5132;
                color: #0f5132;
            }
            QTabBar::tab:hover {
                background: #e7f5ee;
            }
        """)
        self.class_tabs.tabBar().setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        

    def load_classes(self):
        self.class_tabs.clear()
        class_names = get_unique_class_names()
        added_names = set()
        for name in class_names:
            if name not in added_names:
                tab = QWidget()
                layout = QVBoxLayout()
                tab.setLayout(layout)
                self.class_tabs.addTab(tab, name)
                added_names.add(name)
        if self.class_tabs.count() > 0:
            self.class_tabs.setCurrentIndex(0)
            self.load_class_times()

    def _fmt_time_for_db(self, qtime: QTime) -> str:
        return qtime.toString("HH.mm")

    def add_class_dialog(self):
        from PyQt5.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel,
            QCheckBox, QDialogButtonBox, QMessageBox, QTimeEdit, QGridLayout
        )
        from PyQt5.QtCore import QTime

        DAYS = ["Pzt", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cmrtsi", "Pazar"]

        dlg = QDialog(self.main_window)
        dlg.setWindowTitle("Sınıf Ekle")
        root = QVBoxLayout(dlg)

        # Top row: name + optional price
        row_top = QHBoxLayout()
        name_edit = QLineEdit(); name_edit.setPlaceholderText("Sınıf adı (ör. Bachata)")
        price_edit = QLineEdit(); price_edit.setPlaceholderText("Ücret (opsiyonel)")
        row_top.addWidget(QLabel("Sınıf adı:")); row_top.addWidget(name_edit)
        row_top.addWidget(QLabel("Ücret:"));     row_top.addWidget(price_edit)
        root.addLayout(row_top)

        # Day + time grid (tight spacing)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)   # 🔒 tighten label ↔ input
        grid.setVerticalSpacing(4)
        grid.setContentsMargins(0, 0, 0, 0)
        root.addWidget(QLabel("Gün ve saatleri seçin:"))
        root.addLayout(grid)

        day_checks, time_edits = {}, {}
        for i, day in enumerate(DAYS):
            cb = QCheckBox(day)
            te = QTimeEdit()
            te.setDisplayFormat("HH:mm")
            te.setTime(QTime(19, 0))
            te.setEnabled(False)
            cb.stateChanged.connect(lambda _=None, _cb=cb, _te=te: _te.setEnabled(_cb.isChecked()))

            grid.addWidget(cb, i, 0)
            lab = QLabel("Saat:"); lab.setFixedWidth(38)  # 🔒 reduces “empty” gap
            grid.addWidget(lab, i, 1)
            grid.addWidget(te, i, 2)

            day_checks[day] = cb
            time_edits[day] = te

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        root.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        if dlg.exec_() != QDialog.Accepted:
            return

        cname = (name_edit.text() or "").strip()
        if not cname:
            QMessageBox.warning(self.main_window, "Eksik bilgi", "Sınıf adı gerekli.")
            return

        pairs = []
        for d in DAYS:
            if day_checks[d].isChecked():
                pairs.append((d, time_edits[d].time().toString("HH.mm")))  # store as HH.mm

        if not pairs:
            QMessageBox.warning(self.main_window, "Eksik bilgi", "En az bir gün seçmelisiniz.")
            return

        try:
            price = float(price_edit.text().replace(",", ".")) if price_edit.text().strip() else None
        except Exception:
            price = None

        combined_day  = ",".join(d for d, _ in pairs)
        combined_hour = ",".join(h for _, h in pairs)

        if class_instance_exists(cname, combined_day, combined_hour):
            QMessageBox.information(self.main_window, "Bilgi",
                                    f"'{cname}' için bu kombinasyon zaten var:\n{combined_day} / {combined_hour}")
        else:
            add_class(cname, combined_day, combined_hour, price)
            QMessageBox.information(self.main_window, "Tamam",
                                    f"{cname}: {combined_day} – {combined_hour} eklendi.")

        self.load_classes()



    def load_class_times(self):
        from PyQt5.QtWidgets import (
            QWidget, QVBoxLayout, QTabWidget, QTableWidget, QPushButton, QHBoxLayout
        )
        from PyQt5.QtWidgets import QHeaderView, QAbstractItemView

        button_style = """
            QPushButton {
                font-weight: bold;
                font-size: 20px;
                padding: 6px 12px;
                border: 2px solid #000;
                border-radius: 6px;
                background-color: #f0f0f0;
            }
            QPushButton:hover { background-color: #d0d0d0; }
        """

        idx = self.class_tabs.currentIndex()
        if idx == -1:
            return

        class_name = self.class_tabs.tabText(idx)
        times = get_class_times_by_name(class_name)   # [(combined_day, combined_hour), ...]

        current_widget = self.class_tabs.widget(idx)

        # ✅ get or create layout WITHOUT resetting it if it already exists
        layout = current_widget.layout()
        if layout is None:
            layout = QVBoxLayout()
            current_widget.setLayout(layout)
        else:
            # ✅ remove any previous QTabWidget children only (keep the layout)
            for i in reversed(range(layout.count())):
                item = layout.itemAt(i)
                w = item.widget()
                if isinstance(w, QTabWidget):
                    layout.takeAt(i)      # detach from layout
                    w.deleteLater()       # schedule for deletion

        if not times:
            return

        day_hour_tabs = QTabWidget()
        # wider sub-tabs
        day_hour_tabs.tabBar().setStyleSheet("""
            QTabBar::tab {
                min-width: 230px;
                padding: 8px 14px;
                font-size: 18px;
                font-weight: 600;
            }
        """)

        for day_str, hour_str in times:
            days  = [d.strip() for d in str(day_str).split(",")  if d.strip()]
            hours = [h.strip() for h in str(hour_str).split(",") if h.strip()]
            label_text = " - ".join(f"{d} {h}" for d, h in zip(days, hours)) or f"{day_str} {hour_str}"

            sub = QWidget()
            sub_layout = QVBoxLayout(sub)

            table = QTableWidget()
            table.setColumnCount(9)
            table.setHorizontalHeaderLabels([
                "İsim", "Numara", "Başlangıç Tarihi", "Bitiş Tarihi",
                "Kalan Ders", "Not", "KALAN GÜN", "Özellikler", "ID"
            ])
            table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
            table.horizontalHeader().setStretchLastSection(True)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.setSelectionMode(QAbstractItemView.ExtendedSelection)
            table.setStyleSheet("QTableWidget { background-color: #ffe699; font-weight: bold; font-size: 16px; }")

            class_id = get_class_id(class_name, day_str, hour_str)
            self.main_window.student_manager.refresh_student_table(class_id, table)
            sub_layout.addWidget(table)

            row = QHBoxLayout()
            add_btn = QPushButton("Öğrenci ekle"); add_btn.setStyleSheet(button_style)
            add_btn.clicked.connect(lambda _, cid=class_id, tbl=table: self.main_window.add_student_dialog(cid, tbl))
            row.addWidget(add_btn)

            del_btn = QPushButton("Seçili öğrencileri sil"); del_btn.setStyleSheet(button_style)
            del_btn.clicked.connect(lambda _, cid=class_id, tbl=table:
                                    self.main_window.student_manager.delete_selected_students(cid, tbl))
            row.addWidget(del_btn)

            att_btn = QPushButton("Yoklama Göster"); att_btn.setStyleSheet(button_style)
            att_btn.clicked.connect(lambda _, tbl=table: self.show_selected_student_attendance(tbl))
            row.addWidget(att_btn)

            sub_layout.addLayout(row)

            tab_idx = day_hour_tabs.addTab(sub, label_text)
            # keep original combined strings for edit/delete flows
            day_hour_tabs.tabBar().setTabData(tab_idx, (day_str, hour_str))

        # === ESKİLER tab (behaves like a subclass) ===
        esk_class_id = ensure_eskiler_class(class_name)  # creates if missing

        esk_tab = QWidget()
        esk_layout = QVBoxLayout(esk_tab)

        # table
        esk_table = QTableWidget()
        esk_layout.addWidget(esk_table)

        # fill table using the same API as a normal subclass
        # (reuse your existing StudentManager method)
        self.main_window.student_manager.refresh_student_table(esk_class_id, esk_table)

        # same bottom buttons as other subclasses
        btn_row = QHBoxLayout()
        for text, func in [("Uzat", self.main_window.extend_student_courses),
                        ("Seçili öğrencileri sil", self.main_window.delete_selected_student_direct)]:
            btn = QPushButton(text)
            btn.setStyleSheet(button_style)
            # hook: current esk_class_id captured per button
            btn.clicked.connect(lambda _=False, cid=esk_class_id, tbl=esk_table, f=func:
                                f(None, cid, tbl) if f == self.main_window.delete_selected_student_direct
                                else f(None, cid, tbl))
            btn_row.addWidget(btn)
        esk_layout.addLayout(btn_row)

        idx_esk = day_hour_tabs.addTab(esk_tab, "ESKİLER")
        # Put a real (day, hour) marker so your get_current_class_id keeps working
        day_hour_tabs.tabBar().setTabData(idx_esk, ("ESKİLER", "ESKİLER"))

        layout.addWidget(day_hour_tabs)




    def show_selected_student_attendance(self, table_widget):
        selected_items = table_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.main_window, "Öğrenci seçilmedi", "Lütfen yoklama için bir öğrenci satırı seçin.")
            return

        selected_row = selected_items[0].row()
        student_id_item = table_widget.item(selected_row, 8)  # Column 8 is ID

        if student_id_item is None:
            QMessageBox.warning(self.main_window, "Hata", "Bu satır için öğrenci ID'si bulunamadı.")
            return

        student_id_text = student_id_item.text().strip()
        if not student_id_text.isdigit() or student_id_text == "-1":
            QMessageBox.warning(self.main_window, "Hata", "Bu satır için öğrenci ID'si bulunamadı.")
            return

        student_id = int(student_id_text)
        student_name_item = table_widget.item(selected_row, 0)
        student_name = student_name_item.text() if student_name_item else "Unknown"

        attendance_calendar = AttendanceCalendar(student_id, student_name)
        attendance_calendar.exec_()




    def edit_class_instance(self, class_name, day, hour):
        dialog = QDialog(self.main_window)
        dialog.setWindowTitle("Sınıf Bilgisi Düzenle")
        layout = QFormLayout(dialog)

        days_layout = QVBoxLayout()
        day_checks = []
        days_of_week = ["Pzt", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cmrtsi", "Pazar"]
        for d in days_of_week:
            cb = QCheckBox(d)
            if d in day.split(","):
                cb.setChecked(True)
            day_checks.append(cb)
            days_layout.addWidget(cb)
        layout.addRow("Günler:", days_layout)

        hour_edit = QLineEdit(hour)
        layout.addRow("Saat:", hour_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            new_hour = hour_edit.text().strip()
            selected_days = [cb.text() for cb in day_checks if cb.isChecked()]
            if not new_hour or not selected_days:
                QMessageBox.warning(self.main_window, "Eksik Bilgi", "Lütfen saat ve en az bir gün seçin.")
                return
            new_day_str = ",".join(selected_days)
            update_class_instance(class_name, day, hour, new_day_str, new_hour)
            self.load_classes()

    def edit_current_class_instance(self):
        idx_class = self.class_tabs.currentIndex()
        if idx_class == -1:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self.main_window, "Sınıf Yok", "Hiçbir sınıf seçilmedi!")
            return

        class_name = self.class_tabs.tabText(idx_class)
        current_class_widget = self.class_tabs.widget(idx_class)
        day_hour_tabs = current_class_widget.layout().itemAt(0).widget() if current_class_widget and current_class_widget.layout().count() else None
        if not day_hour_tabs:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self.main_window, "Sınıf Yok", "Alt sekme bulunamadı.")
            return

        sub_idx = day_hour_tabs.currentIndex()
        if sub_idx == -1:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self.main_window, "Sınıf Yok", "Bir alt sekme seçin.")
            return

        # We stored (combined_day, combined_hour) in tabData
        data = day_hour_tabs.tabBar().tabData(sub_idx)
        if not data:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self.main_window, "Hata", "Alt sekme bilgisi okunamadı.")
            return

        combined_day, combined_hour = data
        self._edit_class_dialog(class_name, combined_day, combined_hour)

    def _edit_class_dialog(self, class_name: str, combined_day: str, combined_hour: str):
        """
        Modal popup to edit a single class instance's day/hour.
        Handles duplicate target (UNIQUE) and 'database is locked' gracefully.
        """
        # Local imports so the function is self-contained
        import sqlite3
        from PyQt5.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel,
            QComboBox, QPushButton, QMessageBox
        )

        # Basic Turkish days + some common hour slots (fallback if you don't fill dynamically)
        DAYS_FALLBACK = [
            "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"
        ]
        HOURS_FALLBACK = [
            "10.00", "11.00", "12.00", "13.00", "14.00", "15.00",
            "16.00", "17.00", "18.00", "19.00", "20.00", "21.00"
        ]

        # Try to load options from DB if you already have helpers; otherwise use fallbacks
        try:
            from database import get_distinct_days, get_distinct_hours  # optional helpers
            days = get_distinct_days() or DAYS_FALLBACK
            hours = get_distinct_hours() or HOURS_FALLBACK
        except Exception:
            days = DAYS_FALLBACK
            hours = HOURS_FALLBACK

        dlg = QDialog(self.main_window)
        dlg.setWindowTitle(f"Sınıfı Düzenle – {class_name}")
        dlg.setModal(True)

        v = QVBoxLayout(dlg)

        # --- Day row ---
        row_day = QHBoxLayout()
        row_day.addWidget(QLabel("Gün:"))
        day_combo = QComboBox()
        day_combo.addItems(days)
        # Select current
        try:
            idx = days.index(combined_day)
            day_combo.setCurrentIndex(idx)
        except ValueError:
            # if current day not in list, append & select it
            day_combo.addItem(combined_day)
            day_combo.setCurrentText(combined_day)
        row_day.addWidget(day_combo)
        v.addLayout(row_day)

        # --- Hour row ---
        row_hour = QHBoxLayout()
        row_hour.addWidget(QLabel("Saat:"))
        hour_combo = QComboBox()
        hour_combo.addItems(hours)
        try:
            idx = hours.index(combined_hour)
            hour_combo.setCurrentIndex(idx)
        except ValueError:
            hour_combo.addItem(combined_hour)
            hour_combo.setCurrentText(combined_hour)
        row_hour.addWidget(hour_combo)
        v.addLayout(row_hour)

        # --- Buttons ---
        row_btns = QHBoxLayout()
        save_btn = QPushButton("Kaydet")
        cancel_btn = QPushButton("İptal")
        row_btns.addStretch()
        row_btns.addWidget(save_btn)
        row_btns.addWidget(cancel_btn)
        v.addLayout(row_btns)

        def on_save():
            new_day = day_combo.currentText().strip()
            new_hour = hour_combo.currentText().strip()

            # No change?
            if new_day == combined_day and new_hour == combined_hour:
                QMessageBox.information(self.main_window, "Bilgi", "Değişiklik yok.")
                return

            from database import update_class_instance

            try:
                updated = update_class_instance(
                    class_name, combined_day, combined_hour, new_day, new_hour
                )
                if updated:
                    # Refresh UI as you already do elsewhere
                    self.main_window.class_manager.load_class_times()
                    QMessageBox.information(
                        self.main_window, "Tamam",
                        f"'{class_name}' için saat/gün güncellendi:\n"
                        f"{combined_day} {combined_hour} → {new_day} {new_hour}"
                    )
                    dlg.accept()
                else:
                    # Function may return False if nothing changed
                    QMessageBox.information(self.main_window, "Bilgi", "Değişiklik yok.")

            except ValueError as e:
                # Our DB layer raises ValueError("duplicate_class_time") for UNIQUE collisions
                if str(e) == "duplicate_class_time":
                    QMessageBox.warning(
                        self.main_window, "Zaten var",
                        f"'{class_name}' için {new_day} {new_hour} zaten mevcut.\n"
                        f"Lütfen farklı bir gün/saat seçin."
                    )
                else:
                    QMessageBox.warning(self.main_window, "Hata", f"Beklenmeyen hata: {e}")

            except sqlite3.IntegrityError as e:
                # Extra safety: catch raw UNIQUE errors if bubbled up
                QMessageBox.warning(
                    self.main_window, "Hata",
                    f"Güncelleme yapılamadı (benzersiz kısıtlaması):\n{e}"
                )

            except sqlite3.OperationalError as e:
                # Handle 'database is locked' more kindly
                if "database is locked" in str(e).lower():
                    QMessageBox.warning(
                        self.main_window, "Dikkat",
                        "Veritabanı şu anda meşgul. Birkaç saniye sonra tekrar deneyin."
                    )
                else:
                    QMessageBox.warning(self.main_window, "Hata", str(e))

        save_btn.clicked.connect(on_save)
        cancel_btn.clicked.connect(dlg.reject)

        dlg.exec_()



    def delete_specific_class_instance(self, name, day, hour):
        reply = QMessageBox.question(
            self.main_window,
            "Silme Onayı",
            f"{day} {hour} saatindeki {name} sınıfını silmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            from database import delete_class_instance
            delete_class_instance(name, day, hour)
            self.load_classes()


    def delete_current_class_instance(self):
        class_id = self.main_window.get_current_class_id()
        if not class_id:
            QMessageBox.warning(self.main_window, "Sınıf Yok", "Hiçbir sınıf seçilmedi!")
            return
        class_name = self.class_tabs.tabText(self.class_tabs.currentIndex())
        day_hour_tabs = self.class_tabs.widget(self.class_tabs.currentIndex()).layout().itemAt(0).widget()
        label = day_hour_tabs.tabText(day_hour_tabs.currentIndex())
        if label.strip().upper() == "ESKİLER":
            QMessageBox.information(self.main_window, "Bilgi", "Eskiler alt sınıfını silemezsiniz.")
            return
        data = day_hour_tabs.tabBar().tabData(day_hour_tabs.currentIndex())  # ✅
        if not data:
            QMessageBox.warning(self.main_window, "Sınıf Yok", "Hiçbir sınıf seçilmedi!")
            return
        day, hour = data
        if not data:
            QMessageBox.warning(self.main_window, "Sınıf Yok", "Hiçbir sınıf seçilmedi!")
            return
        day, hour = data

        self.delete_specific_class_instance(class_name, day, hour)

    def refresh_left_courses(self):
        from database import update_left_classes_for_all_students
        update_left_classes_for_all_students()
        self.load_class_times()

    