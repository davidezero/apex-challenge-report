@echo off
cd C:\Users\mostcrazygarage\Desktop\apex-challenge-report - Copia
start cmd /k "ngrok http --domain=frank-noted-ghoul.ngrok-free.app 8000"
start cmd /k "python class_manager_apex.py"
exit