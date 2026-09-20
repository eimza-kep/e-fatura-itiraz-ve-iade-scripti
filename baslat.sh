#!/usr/bin/env bash
echo "================================================================="
echo "       E-FATURA İTİRAZ VE İADE YÖNETİM SİSTEMİ BAŞLATICI"
echo "================================================================="
echo ""
echo "Sunucu başlatılıyor: http://localhost:8085"
echo "Yönetim Paneli: http://localhost:8085/admin"
echo ""

if command -v python3 &>/dev/null; then
    python3 server.py
elif command -v python &>/dev/null; then
    python server.py
else
    echo "Hata: Python bulunamadı!"
    exit 1
fi
