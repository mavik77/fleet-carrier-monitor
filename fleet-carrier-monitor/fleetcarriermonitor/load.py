# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox
import csv
import os
import glob
import json
import myNotebook as nb

import datetime
import traceback
import threading

import logging
from companion import CAPIData, SERVER_LIVE, SERVER_LEGACY, SERVER_BETA
from config import appname, config
from typing import Optional

# This could also be returned from plugin_start3()
plugin_name = os.path.basename(os.path.dirname(__file__))

# A Logger is used per 'found' plugin to make it easy to include the plugin's
# folder name in the logging output format.
# NB: plugin_name here *must* be the plugin's folder name as per the preceding
#     code, else the logger won't be properly set up.
logger = logging.getLogger(f'{appname}.{plugin_name}')

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
carrier_id = None
settings_file = "fleetcarrier_config.json"
blinking = False
export_path = ""
export_path_var: Optional[tk.StringVar] = None

# -----------------------------
# File logger (debug to txt)
# -----------------------------
log_file_path = None
_log_lock = threading.Lock()
LOG_MAX_BYTES = 2 * 1024 * 1024  # 2 MB


def _rotate_log_if_needed():
    """Simple rotation: if log exceeds LOG_MAX_BYTES, move it to .1 and start fresh."""
    global log_file_path
    try:
        if log_file_path and os.path.exists(log_file_path):
            if os.path.getsize(log_file_path) > LOG_MAX_BYTES:
                backup = log_file_path + ".1"
                try:
                    if os.path.exists(backup):
                        os.remove(backup)
                except Exception:
                    pass
                os.rename(log_file_path, backup)
    except Exception:
        # Don't ever crash the plugin because of logging
        pass


def log(msg, level="INFO", data=None, exc=None):
    """
    Writes a timestamped line to fcm_debug_log.txt in plugin folder.
    Also prints to EDMC console for convenience.
    """
    global log_file_path
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f'{ts} [{level}] {msg}'
    try:
        if data is not None:
            line += " | " + json.dumps(data, ensure_ascii=False)
        if exc is not None:
            line += " | EXC: " + repr(exc)
    except Exception:
        pass

    # Always print (helps during development)
    try:
        print("[FleetCarrierMonitor]", line)
    except Exception:
        pass

    # File write
    try:
        if not log_file_path:
            return
        with _log_lock:
            _rotate_log_if_needed()
            with open(log_file_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        # Never crash because of logging
        pass


def log_exception(context_msg, e):
    """Write exception + traceback to log file."""
    try:
        tb = traceback.format_exc()
    except Exception:
        tb = ""
    log(context_msg, level="ERROR", data={"traceback": tb}, exc=e)


def _init_logger():
    """Call after plugin_directory is known."""
    global log_file_path
    try:
        if plugin_directory:
            log_file_path = os.path.join(plugin_directory, "fcm_debug_log.txt")
            # Session header
            log("=== FleetCarrierMonitor session started ===", level="INFO")
            log("Logger path", data={"log_file_path": log_file_path})
    except Exception as e:
        # If even logger init fails, still don't crash
        try:
            print("[FleetCarrierMonitor] Logger init error:", e)
        except Exception:
            pass


class CustomCAPIDataEncoder(json.JSONEncoder):
    """Allow for json dumping via specified encoder."""

    def default(self, o):
        """Tell JSON encoder that we're actually just a dict."""
        return o.__dict__

def plugin_start3(plugin_dir):
    global plugin_directory, fuel_alert_threshold, carrier_id, export_path
    plugin_directory = plugin_dir
    _init_logger()
    log("Plugin started", data={"plugin_directory": plugin_directory})
    # logger.info(f"Plugin started. Plugin folder: {plugin_dir}") # TODO - Use instead of log() function

    try:
        path = os.path.join(plugin_directory, "fc_status.csv")
        if os.path.exists(path):
            with open(path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                row = next(reader, None)
                if row:
                    carrier_data.update(row)
                    log("Loaded previous status from CSV", data=row)
        else:
            log("CSV not found (first run?)", data={"path": path})
    except Exception as e:
        log_exception("Failed to read CSV", e)
        # # Automatically includes exception information.
        # logger.exception("Failed to read CSV:") # TODO - Use instead of log() function

    try:
        path = os.path.join(plugin_directory, settings_file)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                fuel_alert_threshold = int(settings.get("fuel_alert_threshold", 200))
                carrier_id = settings.get("carrier_id", None)
                log("Loaded config", data={"fuel_alert_threshold": fuel_alert_threshold, "carrier_id": carrier_id})
        else:
            log("Config not found (will use defaults / auto-detect)", data={"path": path})
    except Exception as e:
        log_exception("Failed to read config", e)
        # # Automatically includes exception information.
        # logger.exception("Failed to read config:") # TODO - Use instead of log() function

    export_path = config.get_str("fleetcarriermonitor_export_path")  # Retrieve saved value from config
    if export_path == "":
        export_path = plugin_dir

    return "Fleet Carrier Monitor"


def plugin_stop():
    log("Plugin stopped")
    # logger.info("Plugin stopped") # TODO - Use instead of log() function

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

    log("UI created (plugin_app)")
    manual_refresh()
    frame.after(refresh_interval_ms, lambda: auto_refresh(frame))
    return frame


def plugin_prefs(parent, cmdr, is_beta):
    global export_path, export_path_var
    def save_settings():
        try:
            value = int(fuel_entry.get())
            cid = carrier_entry.get().strip()
            with open(os.path.join(plugin_directory, settings_file), "w", encoding="utf-8") as f:
                json.dump({
                    "fuel_alert_threshold": value,
                    "carrier_id": cid
                }, f)
            log("Settings saved", data={"fuel_alert_threshold": value, "carrier_id": cid})
            messagebox.showinfo("Settings", "Saved. Restart EDMC to apply.")
        except Exception as e:
            log_exception("Error saving settings", e)
            messagebox.showerror("Error", str(e))

    frame = nb.Frame(parent)
    frame.columnconfigure(2, weight=1)
    nb.Label(frame, text="Alert if fuel below:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
    fuel_entry = nb.EntryMenu(frame)
    fuel_entry.insert(0, str(fuel_alert_threshold))
    fuel_entry.grid(row=0, column=1, padx=10, pady=5, sticky="w")

    nb.Label(frame, text="Your Carrier ID:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
    carrier_entry = nb.EntryMenu(frame)
    if carrier_id:
        carrier_entry.insert(0, carrier_id)
    carrier_entry.grid(row=1, column=1, padx=10, pady=5, sticky="w")

    nb.Label(frame, text="Leave blank to auto-detect from game logs.", wraplength=400).grid(row=1, column=2, columnspan=1, padx=10, pady=5, sticky="w")

    nb.Label(frame, text="Export FC Data folder:").grid(row=2, column=0, sticky="w", padx=10, pady=5)
    export_path_var = tk.StringVar(value=export_path)
    export_path_entry = nb.EntryMenu(frame, textvariable=export_path_var)
    export_path_entry.grid(row=2, column=1, columnspan=2, padx=10, pady=5, sticky="ew")

    nb.Button(frame, text="Save", command=save_settings).grid(row=3, column=0, columnspan=2, pady=10)

    log("Preferences UI opened", data={"cmdr": cmdr, "is_beta": is_beta})
    return frame

def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """
    Save settings.
    """
    global export_path, export_path_var

    # Update internal settings
    export_path = export_path_var.get()

    # Save setting
    config.set('fleetcarriermonitor_export_path', export_path)  # Store new value in config

    save_data_to_csv()

def update_ui():
    try:
        fuel_value = int(carrier_data["fuel"])
    except Exception:
        fuel_value = 0

    fuel_text = "Fuel: " + str(carrier_data["fuel"])
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
        log_exception("Failed to save CSV", e)
        # # Automatically includes exception information.
        # logger.exception("Failed to save CSV:") # TODO - Use instead of log() function

def find_latest_carrier_location():
    try:
        log_dir = os.path.join(os.environ["USERPROFILE"], "Saved Games", "Frontier Developments", "Elite Dangerous")
        journal_files = glob.glob(os.path.join(log_dir, "Journal.*.log"))
        if not journal_files:
            log("No journal files found", level="WARNING", data={"log_dir": log_dir})
            return None

        latest_log = max(journal_files, key=os.path.getmtime)
        with open(latest_log, "r", encoding="utf-8") as f:
            lines = f.readlines()[::-1]
            for line in lines:
                if '"event":"CarrierLocation"' in line:
                    event = json.loads(line)
                    if (not carrier_id) or (str(event.get("CarrierID")) == str(carrier_id)):
                        loc = event.get("StarSystem", "Unknown")
                        log("CarrierLocation found", data={
                            "file": os.path.basename(latest_log),
                            "CarrierID": event.get("CarrierID"),
                            "StarSystem": loc
                        })
                        return loc
    except Exception as e:
        log_exception("Error reading CarrierLocation", e)
        # # Automatically includes exception information.
        # logger.exception("Error reading CarrierLocation from log:") # TODO - Use instead of log() function
    return None


def auto_refresh(frame):
    try:
        loc = find_latest_carrier_location()
        if loc and loc != carrier_data["location"]:
            old = carrier_data["location"]
            carrier_data["location"] = loc
            save_data_to_csv()
            update_ui()
            log("Auto refresh: location updated", data={"from": old, "to": loc})
        else:
            log("Auto refresh tick", level="DEBUG", data={"location": carrier_data.get("location"), "carrier_id": carrier_id})
    except Exception as e:
        log_exception("Auto refresh failed", e)

    frame.after(refresh_interval_ms, lambda: auto_refresh(frame))


def manual_refresh():
    try:
        loc = find_latest_carrier_location()
        if loc:
            old = carrier_data["location"]
            carrier_data["location"] = loc
            save_data_to_csv()
            update_ui()
            log("Manual refresh: location updated", data={"from": old, "to": loc})
        else:
            log("Manual refresh: location not found", level="WARNING", data={"carrier_id": carrier_id})
    except Exception as e:
        log_exception("Manual refresh failed", e)


def journal_entry(cmdr, is_beta, system, station, entry, state):
    global carrier_id
    try:
        event = entry.get("event")
        log("Journal event received", level="DEBUG", data={"event": event})

        if event == "CarrierStats":
            carrier_data["name"] = entry.get("Name", "Unknown")
            carrier_data["fuel"] = str(entry.get("FuelLevel", "0"))
            finance = entry.get("Finance", {})
            carrier_data["credits"] = "{:,}".format(finance.get("CarrierBalance", 0))

            log("CarrierStats parsed", data={
                "name": carrier_data["name"],
                "fuel": carrier_data["fuel"],
                "credits": carrier_data["credits"],
                "CarrierID_in_entry": entry.get("CarrierID")
            })

            # Auto-detect Carrier ID
            if not carrier_id:
                detected_id = str(entry.get("CarrierID"))
                if detected_id and detected_id != "None":
                    carrier_id = detected_id
                    try:
                        config_path = os.path.join(plugin_directory, settings_file)
                        with open(config_path, "w", encoding="utf-8") as f:
                            json.dump({
                                "fuel_alert_threshold": fuel_alert_threshold,
                                "carrier_id": carrier_id
                            }, f)
                        log("Carrier ID auto-detected and saved", data={"carrier_id": carrier_id})
                    except Exception as e:
                        log_exception("Error saving auto Carrier ID", e)

            save_data_to_csv()
            update_ui()

    except Exception as e:
        log_exception("journal_entry failed", e)
	
def capi_fleetcarrier(data):
    """
    Event raised by EDMarketConnector when we have new data on our Fleet Carrier via Frontier CAPI.
    @param data: Fleet Carrier CAPI data dict holding the FC data.
    """
    global export_path

    if data.get('name') is None or data['name'].get('callsign') is None:
        raise ValueError("this isn't possible")

    logger.info(f"Received CAPI FC Data for callsign: {data['name']['callsign']}")

    if not os.path.exists(export_path):
        logger.warning(f"Export folder '{export_path}' does not exist.")
        return

    # Determining source galaxy for the data
    if data.source_host == SERVER_LIVE:
        file_name: str = ""
        file_name += f"FleetCarrier.{data['name']['callsign']}"
        # file_name += time.strftime('.%Y-%m-%dT%H.%M.%S', time.localtime())
        file_name += '.json'

        try:
            path = os.path.join(export_path, file_name)
            logger.info(f"FC data export path: {path}")
            with open(f'{path}', 'wb') as h:
                h.write(json.dumps(data, cls=CustomCAPIDataEncoder,
                                   ensure_ascii=False,
                                   indent=2,
                                   sort_keys=True,
                                   separators=(',', ': ')).encode('utf-8'))

        except Exception as e:
            # Automatically includes exception information.
            logger.exception("Failed to write CAPI FC Data to JSON file:")

    elif data.source_host == SERVER_BETA:
        pass

    elif data.source_host == SERVER_LEGACY:
        pass
