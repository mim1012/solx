# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['phoenix_main.py'],
    pathex=[],
    binaries=[],
    datas=[('src', 'src')],
    hiddenimports=['openpyxl', 'openpyxl.cell._writer', 'requests', 'websockets', 'dataclasses'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'pytest', 'black', 'flake8'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PhoenixTrading',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
