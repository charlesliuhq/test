@echo off
REM ============================================================
REM  在 Windows 上把预测系统打包成单文件 exe (双击即用)
REM  需先安装 Python, 然后双击本脚本或在命令行运行。
REM
REM  重要: PyInstaller 不能跨平台, 必须在 Windows 上运行本脚本
REM        才能生成 Windows 的 exe。生成结果在 dist\ 目录。
REM        若要兼容 Windows 7, 请使用 Python 3.8.x + 对应的
REM        PyInstaller 4.x (新版 PyInstaller 可能不再支持 Win7)。
REM ============================================================

echo [1/2] 安装打包依赖 (pyinstaller)...
python -m pip install --upgrade pyinstaller

echo [2/2] 开始打包...
python -m PyInstaller --clean --noconfirm worldcup_predictor.spec

echo.
echo 打包完成! 可执行文件位于 dist\ 目录:
echo     dist\WorldCupPredictor.exe
echo.
pause
