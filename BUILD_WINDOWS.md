# Build the Windows EXE

Use 64-bit Windows and Python 3.12.

## 1. Open PowerShell in the project folder

```powershell
cd D:\MEDVAI_OPEN_SOURCE_PDF_SUITE
```

## 2. Create a clean virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## 3. Run tests

```powershell
python -m pytest -q
```

## 4. Remove old build results

```powershell
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
```

## 5. Build

```powershell
python -m PyInstaller --clean --noconfirm MedVai_PDF_Suite.spec
```

Expected output:

```text
dist\MedVai_PDF_Suite.exe
```

## 6. Test the EXE

Test Merge, Split, Bates, Numbering, rotated pages, previews, and audit output. Ideally test on a Windows computer without Python installed.

## 7. Create the release ZIP

Run:

```powershell
.\tools\package_release.ps1
```

This creates a Windows release ZIP and a SHA-256 checksum file under `release_output`.
## Windows security notice for the release

The EXE is not digitally signed. Keep `README_FIRST.txt`, `SHA256.txt`, and the Windows security instructions in every release ZIP. Users should verify the checksum and use the Windows **Unblock** option only for a download confirmed to be from the official GitHub Release. Do not advise users to disable antivirus protection.

