from database import get_students_with_zero_kalan_gun
from whatsapp_sender import send_whatsapp_message
from datetime import datetime
import tkinter as tk
from tkinter import messagebox

def clean_number_for_whatsapp(number):
    digits = ''.join(filter(str.isdigit, number))
    if digits.startswith('0'):
        digits = digits[1:]
    return f"+90{digits}"

def show_popup_message(message):
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    messagebox.showinfo("Notification", message)
    root.destroy()

def main():
    today_str = datetime.today().strftime("%d-%m-%Y")

    students = get_students_with_zero_kalan_gun()
    if not students:
        # 🔥 Show a pop-up message if there are no students
        show_popup_message("Ödeme günü gelen öğrenci yok")
        print("[INFO] No students with 0 kalan gün.")
        return

    for student_id, name, number, class_name in students:
        if not number:
            print(f"[WARNING] {name} in numarası yok")
            continue

        # 🔥 Insert the class name dynamically!
        message_text = f"""Sayın üyemiz,

Dans kursuna devamlılığınız için teşekkür ederiz. 
{class_name} dersleri için güncel ödeme tarihi {today_str}’tir. 
Ödeme yaptıysanız lütfen bu mesajı dikkate almayınız.

Saygılarımla,
111 Dans Stüdyos"""

        clean_number = clean_number_for_whatsapp(number)
        send_whatsapp_message(clean_number, message_text)

if __name__ == "__main__":
    main()
