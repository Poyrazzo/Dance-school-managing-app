from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHBoxLayout, QLineEdit, QHeaderView, QFileDialog, QPushButton
)
from PyQt5.QtCore import Qt
from database import get_all_hesap_records, save_all_hesap_records, save_eski_kasa  
from PyQt5.QtGui import QPixmap, QPainter, QFont
from datetime import datetime
import os
import pandas as pd
from pathlib import Path
from database import get_storage_root


PROJECT_ROOT = Path(__file__).resolve().parent

class HesapDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hesap - Kasa Hesabı")
        self.resize(800, 600)

        # Layout
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Title
        title_label = QLabel("<h2>Hesap Tablosu</h2>")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["İsim", "Miktar", "Ödeme Şekli", "Ders", "Not"])
        self.table.setEditTriggers(QTableWidget.AllEditTriggers)
        layout.addWidget(self.table)

        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        # Load from DB
        self.load_data_from_db()

        # Kasa and Eski Kasa
        kasa_inputs_layout = QHBoxLayout()
        for label_text, attr in [("Eski Kasa:", "eski_kasa_input"), ("Kasa:", "kasa_box")]:
            label = QLabel(label_text)
            label.setStyleSheet("font-weight: bold; font-size: 16px;")
            edit = QLineEdit("0.00")
            edit.setStyleSheet("font-weight: bold; font-size: 16px; background-color: #f0f0f0;")
            if attr == "kasa_box":
                edit.setReadOnly(True)
            setattr(self, attr, edit)
            kasa_inputs_layout.addWidget(label)
            kasa_inputs_layout.addWidget(edit)
        layout.addLayout(kasa_inputs_layout)

        self.eski_kasa_input.textChanged.connect(self.update_kasa)

        self.update_kasa()
        self.table.itemChanged.connect(self.on_item_changed)
        self.eski_kasa_input.textChanged.connect(self.on_eski_kasa_changed)

        # Buttons (Delete and Save)
        button_layout = QHBoxLayout()

        delete_button = QPushButton("🗑️ Sil")
        delete_button.setStyleSheet("font-weight: bold; font-size: 14px; background-color: #ffcccc;")
        delete_button.clicked.connect(self.delete_selected_row)
        button_layout.addWidget(delete_button)

        save_button = QPushButton("💾 Excel olarak kaydet")
        save_button.setStyleSheet("font-weight: bold; font-size: 14px; background-color: #cce5ff;")
        save_button.clicked.connect(lambda: (self.save_to_excel(), self.save_as_png()))
        button_layout.addWidget(save_button)

        layout.addLayout(button_layout)

        # Add "+" button at the bottom
        self.add_new_row_button()
        self.load_eski_kasa()
        self.update_kasa()

    def load_data_from_db(self):
        rows = get_all_hesap_records()
        for i, row_data in enumerate(rows):
            if i >= self.table.rowCount():
                self.table.insertRow(i)
            for j, value in enumerate(row_data):
                item = QTableWidgetItem(str(value) if value else "")
                item.setTextAlignment(Qt.AlignCenter)
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                self.table.setItem(i, j, item)
        if not rows:
            self.table.setRowCount(10)

    def on_eski_kasa_changed(self, _text):
        # Update displayed total
        self.update_kasa()
        # Persist immediately (like rows do)
        try:
            txt = self.eski_kasa_input.text().replace(",", ".").strip()
            value = float(txt) if txt else 0.0
            save_eski_kasa(value)
            # optional: print/log
            # print(f"[INFO] Eski Kasa saved: {value}")
        except Exception as e:
            # optional: print/log
            # print(f"[WARN] Could not save Eski Kasa: {e}")
            pass


    def save_data_to_db(self):
        rows_data = []
        for row in range(self.table.rowCount()):
            isim = self.get_cell_text(row, 0)
            miktar = self.get_cell_text(row, 1)
            odeme = self.get_cell_text(row, 2)
            ders = self.get_cell_text(row, 3)
            notlar = self.get_cell_text(row, 4)
            if any([isim, miktar, odeme, ders, notlar]):
                rows_data.append((isim, miktar, odeme, ders, notlar))
        save_all_hesap_records(rows_data)

    def get_cell_text(self, row, col):
        item = self.table.item(row, col)
        return item.text() if item else ""

    def update_kasa(self):
        total = 0
        for row in range(self.table.rowCount()):
            try:
                miktar_item = self.table.item(row, 1)
                payment_item = self.table.item(row, 2)
                if miktar_item and payment_item:
                    miktar_text = miktar_item.text().replace(",", ".").strip()
                    if not miktar_text:
                        continue
                    miktar_value = float(miktar_text)
                    if payment_item.text().strip().upper() not in ("EFT", "KART"):
                        total += miktar_value
            except Exception as e:
                print(f"Skipping row {row} for total calculation due to error: {e}")
                continue

        eski_kasa_text = self.eski_kasa_input.text().replace(",", ".").strip()
        try:
            eski_kasa_value = float(eski_kasa_text) if eski_kasa_text else 0
            total += eski_kasa_value
            # 🛑 Don’t save here! Only display it
        except:
            pass

        self.kasa_box.setText(f"{total:.2f}")


    def on_item_changed(self, item):
        item.setText(item.text().upper())
        font = item.font()
        font.setBold(True)
        item.setFont(font)

        # If last row has at least one filled cell, add a new row button
        last_row = self.table.rowCount() - 1
        if any(self.get_cell_text(last_row, col) for col in range(5)):
            self.add_new_row()

        self.update_kasa()
        self.save_data_to_db()

    def save_to_excel(self):
        from PyQt5.QtWidgets import QMessageBox
        date_str = datetime.today().strftime("%d-%m-%Y")

        dir_path = get_storage_root() / "hesap" / "exceller"
        dir_path.mkdir(parents=True, exist_ok=True)

        path = dir_path / f"{date_str}.xlsx"
        i = 1
        while path.exists():
            path = dir_path / f"{date_str} ({i}).xlsx"
            i += 1

        data = []
        for row in range(self.table.rowCount()):
            row_data = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                row_data.append(item.text() if item else "")
            data.append(row_data)

        df = pd.DataFrame(data, columns=["İsim", "Miktar", "Ödeme Şekli", "Ders", "Not"])
        try:
            df.to_excel(str(path), index=False)
            QMessageBox.information(self, "Başarılı", f"Dosya kaydedildi:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Kaydedilemedi:\n{e}")



    def save_as_png(self):
        from PyQt5.QtWidgets import QMessageBox
        date_str = datetime.today().strftime("%d-%m-%Y")

        dir_path = get_storage_root() / "hesap" / "photo"
        dir_path.mkdir(parents=True, exist_ok=True)

        path = dir_path / f"{date_str}.png"
        i = 1
        while path.exists():
            path = dir_path / f"{date_str} ({i}).png"
            i += 1

        pixmap = self.table.grab()

        extra_height = 50
        new_pixmap = QPixmap(pixmap.width(), pixmap.height() + extra_height)
        new_pixmap.fill(Qt.white)

        painter = QPainter(new_pixmap)
        painter.drawPixmap(0, 0, pixmap)
        painter.setFont(QFont("Arial", 12))
        painter.drawText(10, pixmap.height() + 20, f"Eski Kasa: {self.eski_kasa_input.text()}")
        painter.drawText(10, pixmap.height() + 40, f"Kasa: {self.kasa_box.text()}")
        painter.end()

        if new_pixmap.save(str(path)):
            QMessageBox.information(self, "Başarılı", f"Ekran görüntüsü kaydedildi:\n{path}")
        else:
            QMessageBox.warning(self, "Hata", "PNG kaydedilemedi!")



    def delete_selected_row(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            item.setText("")
        self.update_kasa()
        self.save_data_to_db()

    def add_new_row_button(self):
        # Remove "+" buttons from ALL rows first
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 0):
                self.table.removeCellWidget(row, 0)

        # Insert new row at the bottom
        row_count = self.table.rowCount()
        self.table.insertRow(row_count)

        # Add "+" button to the new bottom row
        add_btn = QPushButton("+")
        add_btn.clicked.connect(self.add_new_row)
        self.table.setCellWidget(row_count, 0, add_btn)


    def add_new_row(self):
        row_count = self.table.rowCount()
        self.table.insertRow(row_count)
        self.add_new_row_button()  # Move "+" button to new bottom

    def load_eski_kasa(self):
        from database import get_eski_kasa  # You need to define this in database.py
        eski_kasa = get_eski_kasa()
        if eski_kasa is not None:
            self.eski_kasa_input.setText(f"{eski_kasa:.2f}")

    def closeEvent(self, event):
        try:
            eski_kasa_text = self.eski_kasa_input.text().replace(",", ".").strip()
            eski_kasa_value = float(eski_kasa_text) if eski_kasa_text else 0
            save_eski_kasa(eski_kasa_value)
            print(f"[INFO] Saved eski kasa: {eski_kasa_value}")
        except Exception as e:
            print(f"[ERROR] Failed to save eski kasa: {e}")
        event.accept()
