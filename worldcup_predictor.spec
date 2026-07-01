# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller 打包配置文件。
# 在 Windows 上运行:  python -m PyInstaller --clean --noconfirm worldcup_predictor.spec
# 生成:  dist\WorldCupPredictor.exe  (单文件, 无控制台窗口)
#
# 说明:
#   - datas 会把示例数据一并打包进 exe, 首次运行时可用。
#   - console=False 使双击时不弹出黑色命令行窗口 (纯 GUI)。

block_cipher = None

a = Analysis(
    ['worldcup_predictor.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('historical_matches.csv', '.'),
    ],
    hiddenimports=['livedata'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='WorldCupPredictor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
