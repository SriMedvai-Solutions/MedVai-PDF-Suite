# First public release checklist

- [ ] Source tests pass with `python -m pytest -q`.
- [ ] EXE opens on Windows 10/11 x64.
- [ ] Merge only works.
- [ ] Split by range works and rejects invalid ranges.
- [ ] Split by pages per file creates a smaller final part when necessary.
- [ ] Continuous Bates works across several PDFs.
- [ ] Selective Bates merges unselected PDFs without stamping them.
- [ ] Numbering continues across the full merged PDF.
- [ ] Rotated pages keep the chosen visual placement.
- [ ] Main output folder contains the PDF, Audit DOCX, and `Technical_Audit_Files`.
- [ ] No confidential test files are present.
- [ ] `build`, `dist`, caches, local settings, and generated outputs are not committed.
- [ ] Release ZIP contains the EXE, README_FIRST.txt, LICENSE, notices, and checksums.
- [ ] README, release notes, and README_FIRST.txt contain the Windows security and Unblock instructions.
- [ ] SHA256.txt matches the final EXE included in the release ZIP.
- [ ] Git tag matches the internal version: `v3.0.5-beta`.
- [ ] GitHub release is marked as a pre-release.
