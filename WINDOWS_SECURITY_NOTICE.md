# Windows security notice

MedVai PDF Suite is distributed as a free, open-source Windows EXE. The EXE is not digitally signed. Windows Defender SmartScreen or another antivirus may show an **Unknown publisher** message, block the file, or ask for confirmation.

A warning does not by itself prove that a file is unsafe. Always verify the download before allowing it to run.

## Safe download and verification

1. Download `MedVai_PDF_Suite_Windows_x64_*.zip` only from the official MedVai PDF Suite GitHub Release.
2. Scan the ZIP or EXE using Microsoft Defender or your normal antivirus.
3. Open `SHA256.txt` from the release ZIP.
4. In PowerShell, run:

```powershell
Get-FileHash .\MedVai_PDF_Suite.exe -Algorithm SHA256
```

5. Confirm that the displayed SHA-256 value exactly matches the value in `SHA256.txt`.

## Unblock the downloaded file

It is best to unblock the downloaded ZIP before extracting it:

1. Right-click the downloaded ZIP.
2. Choose **Properties**.
3. If **Unblock** appears, select it.
4. Choose **Apply → OK**.
5. Extract the ZIP again.

If the EXE still has an **Unblock** option, repeat the same steps for `MedVai_PDF_Suite.exe`.

## SmartScreen message

If Windows shows **Windows protected your PC**:

1. Confirm the file came from the official release.
2. Confirm the SHA-256 value matches.
3. Choose **More info → Run anyway**.

Do this only after verification. Do not disable Microsoft Defender or another antivirus. On a company-managed computer, ask the IT administrator to review or allow the application.

## Reporting a problem

Open a GitHub issue without uploading confidential PDFs, or contact Ramakrishnan Chinnasamy on LinkedIn:

https://www.linkedin.com/in/ramakrishnan-chinnasamy-558321b/
