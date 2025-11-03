from PyQt5.QtWidgets import QDialog, QVBoxLayout, QCalendarWidget, QLabel, QPushButton, QMessageBox, QHBoxLayout
from PyQt5.QtCore import QDate, Qt
from PyQt5.QtGui import QPainter, QColor, QFont, QBrush
from database import get_attendance_for_student, add_attendance, remove_attendance_for_student
from datetime import datetime


class MyCalendarWidget(QCalendarWidget):
    def __init__(self, attendance_dates, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attendance_dates = attendance_dates

    def paintCell(self, painter, rect, date):
        super().paintCell(painter, rect, date)  # Let default paint first

        date_str = date.toString("yyyy-MM-dd")
        painter.save()

        if date <= QDate.currentDate():  # <= to include today
            if date_str in self.attendance_dates:
                painter.setBrush(QColor(144, 255,144))  # semi-transparent green
            else:
                painter.setBrush(QColor(255, 0, 0))  # semi-transparent red
            painter.setPen(Qt.NoPen)
            painter.drawRect(rect)

        # ✅ Draw the day number
        painter.setPen(Qt.black)
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(rect, Qt.AlignCenter, str(date.day()))

        # ✅ If this date is the selected date, draw a blue border
        if date == self.selectedDate():
            painter.setPen(QColor(0, 120, 215))  # bright blue
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect.adjusted(1, 1, -1, -1))  # inner border

        painter.restore()




class AttendanceCalendar(QDialog):
    def __init__(self, student_id, student_name):
        super().__init__()
        self.student_id = student_id
        self.student_name = student_name
        self.setWindowTitle(f"Attendance for {student_name}")
        self.setMinimumSize(600, 500)

        layout = QVBoxLayout(self)
        self.label = QLabel(f"<h3>Attendance record for <b>{student_name}</b></h3>")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        # Load attendance dates
        self.attendance_dates = set(get_attendance_for_student(student_id))

        # Custom calendar widget
        self.calendar = MyCalendarWidget(self.attendance_dates)
        self.calendar.setGridVisible(True)
        layout.addWidget(self.calendar)

        # Buttons
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ Add Attendance")
        add_btn.clicked.connect(self.add_attendance_for_selected_day)
        btn_layout.addWidget(add_btn)

        remove_btn = QPushButton("➖ Remove Attendance")
        remove_btn.clicked.connect(self.remove_attendance_for_selected_day)
        btn_layout.addWidget(remove_btn)
        layout.addLayout(btn_layout)

        # OK Button
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)

        # Legend
        legend = QLabel("🟩 Attended | 🟥 Absent (past days)")
        legend.setAlignment(Qt.AlignCenter)
        layout.addWidget(legend)

    def add_attendance_for_selected_day(self):
        selected_date = self.calendar.selectedDate()
        date_str = selected_date.toString("yyyy-MM-dd")
        add_attendance(self.student_id, date_str)
        self.attendance_dates.add(date_str)
        QMessageBox.information(self, "Success", f"Added attendance for {date_str}.")
        self.calendar.update()

    def remove_attendance_for_selected_day(self):
        selected_date = self.calendar.selectedDate()
        date_str = selected_date.toString("yyyy-MM-dd")

        if date_str not in self.attendance_dates:
            QMessageBox.warning(self, "Not Found", f"No attendance record for {date_str}.")
            return

        reply = QMessageBox.question(
            self,
            "Remove Attendance",
            f"Remove attendance for {date_str}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            remove_attendance_for_student(self.student_id, date_str)
            self.attendance_dates.discard(date_str)
            QMessageBox.information(self, "Attendance Removed", f"Removed attendance for {date_str}.")
            self.calendar.update()

    def mark_attendance(self, student_id, class_id, table_widget):
        today_str = datetime.today().strftime("%Y-%m-%d")
        add_attendance(student_id, today_str)
        QMessageBox.information(self, "Attendance Recorded", f"Marked attendance for today ({today_str})")

