# Steam OSINT Report Builder

Tkinter desktop utility for public and owner-authorized Steam OSINT collection.

## Run

```powershell
python steam_osint_report_builder.py
```

On startup, the launcher checks for `requests`, `beautifulsoup4`, `networkx`, and `matplotlib`. Missing runtime packages are installed automatically from `requirements.txt` before the GUI loads. `install_requirements.bat` is included as a manual fallback and also installs `requirements-build.txt` for packaging.

## Optional Build

```powershell
pyinstaller --noconfirm --onedir --windowed --name SteamOSINTReportBuilder steam_osint_report_builder.py
```

## Boundaries

This project only uses public Steam Community pages or official Steam Web API endpoints. It does not automate login, bypass privacy settings, harvest credentials, or access private data.
