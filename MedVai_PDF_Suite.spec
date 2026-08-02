# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['pdf_suite_gui.py'],
    pathex=['.'],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=[
        'customtkinter',
        'tkinter',
        'tkinter.ttk',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PyPDF2',
        'reportlab',
        'reportlab.pdfgen',
        'reportlab.lib.pagesizes',
        'reportlab.lib.colors',
        'gui_common',
        'medvai_core',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MedVai_PDF_Suite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='assets\\logo.ico',
)
