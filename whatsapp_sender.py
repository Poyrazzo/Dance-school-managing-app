# whatsapp_sender.py
import pywhatkit as kit
from datetime import datetime
import tkinter as tk
from tkinter import messagebox

def show_popup_message(message):
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    messagebox.showinfo("WhatsApp Notification", message)
    root.destroy()

def clean_number_for_whatsapp(number):
    digits = ''.join(filter(str.isdigit, number))
    if digits.startswith('0'):
        digits = digits[1:]
    return f"+90{digits}"

def send_whatsapp_message(to_number, message, delay_minutes=1):
    # Show the info popup
    show_popup_message("30 saniye içerisinde whatsapp açılacak ve 10 saniye içinde mesaj gönderilecek.")

    now = datetime.now()
    send_hour = now.hour
    send_minute = now.minute + delay_minutes

    # Adjust for overflow
    if send_minute >= 60:
        send_minute -= 60
        send_hour = (send_hour + 1) % 24

    kit.sendwhatmsg(to_number, message, send_hour, send_minute, wait_time=10, tab_close=True)
    print(f"[INFO] Scheduled WhatsApp message to {to_number} at {send_hour}:{send_minute}")
