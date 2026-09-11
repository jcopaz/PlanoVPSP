```cmd
   @echo off
   echo ===================================================
   echo    Iniciando o Dashboard de Manutencao...
   echo    Por favor, aguarde a tela carregar.
   echo ===================================================
   
   :: Entra na pasta onde este arquivo .bat esta salvo
   cd /d "%~dp0"
   
   :: Acessa o Python portatil e manda rodar o seu app.py
   ".\python_portatil\python\python.exe" -m streamlit run app.py
   
   pause