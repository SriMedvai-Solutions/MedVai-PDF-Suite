# Contributing

Contributions are welcome.

## Before opening an issue

- Do not upload confidential, medical, legal, client, or personally identifying documents.
- Reproduce the issue with a small synthetic PDF whenever possible.
- State the Windows version, Python version, operation selected, and exact message shown.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Tests

Run all tests before submitting a pull request:

```powershell
python -m pytest -q
```

Also test the GUI manually on Windows when changing layout, previews, output paths, Bates, numbering, or splitting.

## Pull requests

- Keep changes focused.
- Explain the problem and the exact behaviour changed.
- Add or update tests for functional changes.
- Do not commit generated PDFs, audits, logs, EXEs, `build`, `dist`, caches, or private data.
- Keep the project under GNU AGPL v3.0 only.
