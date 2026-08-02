# Third-party notices

MedVai PDF Suite uses the following open-source components. Full licence files for the main runtime dependencies are stored in `third_party_licenses/`.

| Component | Purpose | Licence |
|---|---|---|
| PyMuPDF / MuPDF | PDF rendering, stamping, page inspection, and verification | GNU AGPL v3 or Artifex commercial licence; this project uses the AGPL option |
| pypdf | PDF reading and writing support | BSD 3-Clause |
| CustomTkinter | Desktop user interface | MIT |
| python-docx | Audit DOCX generation | MIT |
| Pillow | Image handling and previews | MIT-CMU / HPND-style licence |
| Python / Tkinter | Python runtime and standard GUI toolkit | Python Software Foundation licence and applicable Tcl/Tk licences |
| PyInstaller | Windows executable packaging | GPL with the PyInstaller bootloader exception |

The dependency names and trademarks belong to their respective owners. MedVai PDF Suite is not affiliated with or endorsed by those projects.

PyMuPDF and MuPDF are available under an open-source AGPL licence or a commercial licence. This repository and its source distribution use the AGPL route, and the complete GNU AGPL v3 text is included as `LICENSE`.

Anyone creating a binary release should distribute `LICENSE`, this notice, and the `third_party_licenses` folder beside the executable or inside the downloadable release ZIP.
