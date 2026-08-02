# MedVai PDF Suite

MedVai PDF Suite is a free, open-source, offline Windows application for:

- merging PDFs;
- splitting PDFs by page range or pages per file;
- continuous or selective Bates numbering;
- continuous page numbering;
- visual placement previews;
- page-by-page verification and audit reporting.

PDFs stay on the user's computer. The application does not upload documents or require an online account.

## Download for Windows

Open the repository's **Releases** section and download the latest Windows x64 ZIP. Extract the ZIP, then run `MedVai_PDF_Suite.exe`.

### Windows security notice

The Windows EXE is not digitally signed. Windows Defender SmartScreen or another antivirus may show **Unknown publisher**, block the file, or ask for confirmation. This can happen with a new open-source EXE.

Before running it:

1. Download it only from the official GitHub Release.
2. Scan the downloaded ZIP or EXE with Microsoft Defender or your antivirus.
3. Compare the EXE's SHA-256 value with `SHA256.txt` included in the release ZIP.
4. Right-click the downloaded ZIP, choose **Properties**, and select **Unblock** if that option appears. Then choose **Apply** and extract the ZIP again.
5. If the EXE itself still shows **Unblock** in Properties, select it and choose **Apply**.
6. If SmartScreen shows **Windows protected your PC**, choose **More info → Run anyway** only after confirming the official source and matching SHA-256 value.

Do not disable your antivirus. On a company-managed computer, contact the IT administrator if the application is blocked. See [WINDOWS_SECURITY_NOTICE.md](WINDOWS_SECURITY_NOTICE.md) for the full instructions.

## Main workflow

1. Select **Merge PDFs**, **Apply Bates**, and/or **Apply Numbering**.
2. Select the input folder.
3. Open **Preview & Arrange PDFs** to check the order.
4. Open the Bates or numbering preview and save the placement.
5. Validate and run.
6. Review the generated PDF and Audit DOCX.

Folder imports use natural order, such as `1.pdf`, `2.pdf`, `10.pdf`. The saved arrangement controls the final merge order.

## Bates modes

### Continuous Bates across all PDFs

One Bates sequence continues through every PDF in the arranged merge list.

### Separate Bates settings for each PDF

All PDFs still merge. Only the chosen PDFs receive Bates numbering. Unselected PDFs stay in the merged output without Bates. The same PDF may be added more than once after confirmation.

## Page numbering

When PDFs are merged, page numbering always continues across the complete merged PDF. Available patterns include:

- `{n}` → `1`
- `Page {n}` → `Page 1`
- `Page-{n}` → `Page-1`
- `Page #{n}` → `Page #1`
- `Pg. {n}` → `Pg. 1`
- `[{n}]` → `[1]`
- `({n})` → `(1)`
- `-{n}-` → `-1-`
- `PAGE {n}` → `PAGE 1`
- `P-{n}` → `P-1`

Custom patterns must contain `{n}`.

## Output structure

The normal output folder contains the main PDF and the human-readable Audit DOCX. Technical CSV maps and the process log are stored separately:

```text
MedVai_Output_CaseName/
├── CaseName_Merged_Bates_Numbered.pdf
├── CaseName_Merged_Bates_Numbered_Audit.docx
└── Technical_Audit_Files/
    ├── Page_Map.csv
    ├── Bates_Map.csv
    ├── Stamp_Verification.csv
    └── Process_Log.txt
```

Existing files are not silently overwritten. The tool adds `_1`, `_2`, and so on.

## Result messages

- **Completed and Verified** — selected operations were completed and verified.
- **Completed — Needs Review** — an output was created, but a page or fallback action needs checking.
- **Could Not Complete — Needs Review** — a safe output could not be created, for example because the source was locked or unreadable.

Always review the generated PDF and Audit DOCX before using the output in a legal or production matter.

## Run from source

Python 3.12 is recommended on Windows.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python pdf_suite_gui.py
```

## Run automated tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Build the Windows EXE

See [BUILD_WINDOWS.md](BUILD_WINDOWS.md).

## Use your own logo

Users may replace the logo for personal or internal use. Replace:

- `assets/logo.png` for the header;
- `assets/logo.ico` for the Windows application icon.

Keep the same filenames, then rebuild the EXE. Read [BRANDING.md](BRANDING.md) before distributing a customized version.

## Support and feedback

MedVai PDF Suite is completely free and open source.

For a problem, open a GitHub issue without attaching confidential or private documents, or contact **Ramakrishnan Chinnasamy** on LinkedIn:

https://www.linkedin.com/in/ramakrishnan-chinnasamy-558321b/

If this tool is useful and you know a law firm that needs medical chronologies, narrative summaries, or medical-record review support, please refer them to **Sri MedVai Solutions**.

## Licence

Copyright (C) 2026 Ramakrishnan Chinnasamy.

MedVai PDF Suite is licensed under the **GNU Affero General Public License v3.0 only**. See [LICENSE](LICENSE). This licence choice is compatible with the project's use of PyMuPDF under its open-source AGPL option. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

The software is provided without warranty.
