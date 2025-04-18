# Fleet Carrier Monitor

Fleet Carrier Monitor is a plugin for EDMarketConnector (EDMC) that provides live monitoring of your Fleet Carrier in Elite Dangerous.

## ✨ Features

- Displays:
  - Carrier name
  - Current location (read from game logs)
  - Fuel level
  - Credit balance
- Low fuel alert with blinking red warning
- Customizable fuel alert threshold
- Automatic data refresh every 30 seconds
- Configuration saved between sessions
- Compatible with EDMC 5.0+

## 🔧 Installation

1. Download or clone this repository.
2. Copy the `fleetcarriermonitor` folder into your EDMC plugins directory:

**Path example (Windows):**
```
C:\Users\YourUsername\AppData\Local\EDMarketConnector\plugins
```

3. Launch EDMC.
4. Go to `Settings → Settings...` and find the `FleetCarrierMonitor` tab.
5. Set your preferred fuel alert threshold and save.

## 📁 Files

- `load.py` — the plugin logic
- `fleetcarrier_config.json` — stores your fuel alert threshold
- `fc_status.csv` — stores last known carrier status

## 📜 License

MIT — use it, modify it, share it!
