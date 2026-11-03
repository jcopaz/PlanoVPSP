@echo off
echo ===================================================
echo    Iniciando o Dashboard de Manutencao...
echo    Por favor, aguarde a tela carregar.
echo ===================================================

:: Entra na pasta onde este arquivo .bat esta salvo
cd /d "%~dp0"

:: Usa, nesta ordem: .venv do projeto, Python portatil, Python instalado no PC
if exist ".\.venv\Scripts\python.exe" (
    ".\.venv\Scripts\python.exe" -m streamlit run app.py
) else if exist ".\python_portatil\python\python.exe" (
    ".\python_portatil\python\python.exe" -m streamlit run app.py
) else (
    python -m streamlit run app.py
)

pause
