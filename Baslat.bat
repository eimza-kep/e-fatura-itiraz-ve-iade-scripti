@echo off
chcp 65001 >nul
echo =================================================================
echo        E-FATURA İTİRAZ VE İADE YÖNETİM SİSTEMİ BAŞLATICI
echo =================================================================
echo.
echo Sunucu hazırlanıyor ve başlatılıyor...
echo Port: 8085
echo.
start "" http://localhost:8085
python server.py
pause
