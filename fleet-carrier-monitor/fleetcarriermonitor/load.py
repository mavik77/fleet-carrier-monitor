# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox
import csv
import os
import glob
import json
import myNotebook as nb

carrier_data = {
    "name": "Unknown",
    "location": "Unknown",
    "fuel": "0",
    "credits": "0"
}

ui_labels = {}
plugin_directory = ""
refresh_interval_ms = 30000
fuel_alert_threshold = 200
blinking = False
settings_file = "fleetcarrier_config.json"

def plugin_start3(plugin_dir):
    global plugin_directory, fuel_alert_threshold
    plugin_directory = plugin_dir
    print("[FleetCarrierMonitor] Plugin with TWH-style settings loaded")

    try:
        path = os.path.join(plugin_directory, "fc_status.csv")
        if os.path.exists(path):
            with open(path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                row = next(reader, None)
                if row:
                    carrier_data.update(row)
    except Exception as e:
        print("[FleetCarrierMonitor] Failed to read CSV:", e)

    try:
        path = os.path.join(plugin_directory, settings_file)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                fuel_alert_threshold = int(settings.get("fuel_alert_threshold", 200))
    except Exception as e:
        print("[FleetCarrierMonitor] Failed to read config:", e)

    return "Fleet Carrier Monitor"

def plugin_stop():
    print("[FleetCarrierMonitor] Plugin stopped")

def plugin_app(parent):
    frame = tk.Frame(parent, bg="#1e1e1e")
    tk.Label(frame, text="Fleet Carrier Monitor", font=("Arial", 14, "bold"), fg="orange", bg="#1e1e1e").pack(pady=10)

    ui_labels["name"] = tk.Label(frame, text="Name: " + carrier_data["name"], fg="white", bg="#1e1e1e")
    ui_labels["location"] = tk.Label(frame, text="Location: " + carrier_data["location"], fg="white", bg="#1e1e1e")
    ui_labels["fuel"] = tk.Label(frame, text="Fuel: " + carrier_data["fuel"], fg="white", bg="#1e1e1e")
    ui_labels["credits"] = tk.Label(frame, text="Credits: " + carrier_data["credits"], fg="white", bg="#1e1e1e")

    for lbl in ui_labels.values():
        lbl.pack(pady=2)

    tk.Button(frame, text="Manual Refresh", command=manual_refresh, bg="#333333", fg="white").pack(pady=10)
    frame.after(refresh_interval_ms, lambda: auto_refresh(frame))
    return frame

def plugin_prefs(parent, cmdr, is_beta):
    def save_settings():
        try:
            value = int(entry.get())
            with open(os.path.join(plugin_directory, settings_file), "w", encoding="utf-8") as f:
                json.dump({"fuel_alert_threshold": value}, f)
            messagebox.showinfo("Settings", "Saved. Restart EDMC to apply.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    frame = nb.Frame(parent)
    nb.Label(frame, text="Alert if fuel below:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
    entry = nb.EntryMenu(frame)
    entry.insert(0, str(fuel_alert_threshold))
    entry.grid(row=0, column=1, padx=10, pady=5)
    nb.Button(frame, text="Save", command=save_settings).grid(row=1, column=0, columnspan=2, pady=10)

    return frame

def update_ui():
    fuel_value = int(carrier_data["fuel"])
    fuel_text = "Fuel: " + carrier_data["fuel"]
    if fuel_value < fuel_alert_threshold:
        fuel_text += " 🔥⚠️ LOW FUEL!"
        ui_labels["fuel"].config(fg="red")
        start_blinking()
    else:
        ui_labels["fuel"].config(fg="white")
        stop_blinking()
    ui_labels["fuel"].config(text=fuel_text)
    ui_labels["name"].config(text="Name: " + carrier_data["name"])
    ui_labels["location"].config(text="Location: " + carrier_data["location"])
    ui_labels["credits"].config(text="Credits: " + carrier_data["credits"])

def start_blinking():
    global blinking
    if not blinking:
        blinking = True
        blink_label()

def stop_blinking():
    global blinking
    blinking = False

def blink_label():
    if not blinking:
        return
    current = ui_labels["fuel"].cget("fg")
    new_color = "red" if current == "#1e1e1e" else "#1e1e1e"
    ui_labels["fuel"].config(fg=new_color)
    ui_labels["fuel"].after(500, blink_label)

def save_data_to_csv():
    try:
        path = os.path.join(plugin_directory, "fc_status.csv")
        with open(path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=carrier_data.keys())
            writer.writeheader()
            writer.writerow(carrier_data)
    except Exception as e:
        print("[FleetCarrierMonitor] Failed to save CSV:", e)

def find_latest_carrier_location():
    try:
        log_dir = os.path.join(os.environ["USERPROFILE"], "Saved Games", "Frontier Developments", "Elite Dangerous")
        journal_files = glob.glob(os.path.join(log_dir, "Journal.*.log"))
        if not journal_files:
            return None
        latest_log = max(journal_files, key=os.path.getmtime)
        with open(latest_log, "r", encoding="utf-8") as f:
            lines = f.readlines()[::-1]
            for line in lines:
                if '"event":"CarrierLocation"' in line:
                    event = json.loads(line)
                    return event.get("StarSystem", "Unknown")
    except Exception as e:
        print("[FleetCarrierMonitor] Error reading CarrierLocation from log:", e)
    return None

def auto_refresh(frame):
    loc = find_latest_carrier_location()
    if loc and loc != carrier_data["location"]:
        carrier_data["location"] = loc
        save_data_to_csv()
        update_ui()
    frame.after(refresh_interval_ms, lambda: auto_refresh(frame))

def manual_refresh():
    loc = find_latest_carrier_location()
    if loc:
        carrier_data["location"] = loc
        save_data_to_csv()
        update_ui()

def journal_entry(cmdr, is_beta, system, station, entry, state):
    event = entry.get("event")
    if event == "CarrierStats":
        carrier_data["name"] = entry.get("Name", "Unknown")
        carrier_data["fuel"] = str(entry.get("FuelLevel", "0"))
        finance = entry.get("Finance", {})
        carrier_data["credits"] = "{:,}".format(finance.get("CarrierBalance", 0))
        save_data_to_csv()
        update_ui()
