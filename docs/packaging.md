# Packaging Notes

The project is structured so it can later be packaged as a macOS `.app` bundle.

## PyInstaller

Install PyInstaller inside the same virtual environment:

```bash
cd "/Users/usmanali/Desktop/untitled folder/dev_scratchpad"
.venv/bin/python -m pip install pyinstaller
.venv/bin/pyinstaller \
  --windowed \
  --name "Dev Scratchpad" \
  --collect-all PySide6 \
  app/main.py
```

The generated app bundle will be under `dist/Dev Scratchpad.app`.

## Briefcase

Briefcase is another good fit if you want a more native Python packaging workflow:

```bash
.venv/bin/python -m pip install briefcase
```

Then add Briefcase metadata to `pyproject.toml` and run:

```bash
.venv/bin/briefcase create macOS
.venv/bin/briefcase build macOS
.venv/bin/briefcase run macOS
```

## Icons and Signing

For local use, an unsigned app is usually fine. For distribution outside your Mac, add:

- a `.icns` app icon
- Apple code signing
- notarization
- hardened runtime settings if distributing broadly

## Storage Location

The app uses Qt's `QStandardPaths.AppDataLocation`, so packaged builds continue storing notes in the user's application support location rather than inside the app bundle.
