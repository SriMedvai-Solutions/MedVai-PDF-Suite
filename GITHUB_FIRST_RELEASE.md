# GitHub first release steps

## 1. Create the repository

Suggested repository name:

```text
MedVai-PDF-Suite
```

Choose **Public**. Do not ask GitHub to create another README, licence, or `.gitignore`, because they are already included here.

## 2. Upload the source

Upload the contents of this folder to the repository root. Do not upload the outer ZIP as the source repository.

Confirm that GitHub shows:

- `README.md`
- `LICENSE`
- `pdf_suite_gui.py`
- `medvai_core/`
- `tests/`
- `.github/`

Do not upload local `build`, `dist`, cache, output, or test-document folders.

## 3. Create the Windows release ZIP

Place the tested EXE at:

```text
dist\MedVai_PDF_Suite.exe
```

Then run:

```powershell
.\tools\package_release.ps1
```

The ZIP will be created under `release_output` and will include the EXE, checksum, licence, notices, and user instructions.

## 4. Create the first GitHub Release

Suggested tag:

```text
v3.0.5-beta
```

Suggested release title:

```text
MedVai PDF Suite — First Public Beta
```

Mark it as a **pre-release** and upload the generated Windows x64 ZIP.

Suggested release notes:

```text
First public beta of MedVai PDF Suite.

Features:
- Offline PDF merge and split
- Continuous and selective Bates numbering
- Continuous page numbering
- Visual Bates and numbering placement
- Rotation-aware stamping
- Per-page verification and Audit DOCX
- Technical audit files stored in a separate subfolder

Windows 10/11 x64. No Python installation is required for the EXE release.

Windows security notice:
- The EXE is not digitally signed, so SmartScreen or antivirus software may show Unknown publisher or block it.
- Download only from this official GitHub Release.
- Scan the download and compare the EXE SHA-256 with SHA256.txt.
- If Unblock appears in the ZIP or EXE Properties, select it and choose Apply.
- Use More info → Run anyway only after confirming the official source and checksum.
- Do not disable antivirus; company users should contact their IT administrator if blocked.

Please review the generated PDF and Audit DOCX before using output in a legal or production matter.
```
