import http.server
import socketserver
import json
import sqlite3
import os
import sys
import random
from urllib.parse import urlparse

# Add current and scripts directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from scripts.ubl_helper import (
    parse_ubl_xml,
    validate_kep_address,
    calculate_ttk_deadline,
    validate_evidence
)

PORT = int(os.environ.get("PORT", 8085))
DB_FILE = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "fatura_itirazlar.db"))

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoice_objections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_code TEXT UNIQUE,
            invoice_number TEXT,
            invoice_uuid TEXT,
            invoice_date TEXT,
            received_date TEXT,
            deadline_date TEXT,
            invoice_amount REAL,
            seller_title TEXT,
            seller_vkn TEXT,
            seller_kep TEXT,
            buyer_title TEXT,
            buyer_vkn TEXT,
            authorized_person TEXT,
            contact_info TEXT,
            buyer_kep TEXT,
            reason_category TEXT,
            notification_channel TEXT,
            evidence_type TEXT,
            evidence_barcode TEXT,
            detailed_reason TEXT,
            status TEXT DEFAULT 'İtiraz Gönderildi (KEP/Noter)',
            created_at TEXT
        )
    """)

    # Mevcut tablolarda sütun eksikse ekle (Migration)
    cur.execute("PRAGMA table_info(invoice_objections)")
    existing_cols = [col[1] for col in cur.fetchall()]
    new_cols = {
        "invoice_uuid": "TEXT",
        "deadline_date": "TEXT",
        "evidence_type": "TEXT",
        "evidence_barcode": "TEXT"
    }
    for col_name, col_type in new_cols.items():
        if col_name not in existing_cols:
            try:
                cur.execute(f"ALTER TABLE invoice_objections ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

    conn.commit()
    conn.close()

class ObjectionHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self.send_file("index.html", "text/html; charset=utf-8")
        elif path in ("/admin", "/admin.html"):
            self.send_file("admin.html", "text/html; charset=utf-8")
        elif path == "/health":
            self.send_json({"status": "ok", "app": "e-fatura-itiraz-ve-iade-scripti", "port": PORT})
        elif path == "/api/itirazlar":
            self.handle_get_itirazlar()
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/itiraz-et":
            self.handle_create_itiraz()
        elif path == "/api/durum-guncelle":
            self.handle_update_status()
        elif path == "/api/parse-ubl":
            self.handle_parse_ubl()
        elif path == "/api/validate-kep":
            self.handle_validate_kep()
        elif path == "/api/calculate-deadline":
            self.handle_calculate_deadline()
        else:
            self.send_error(404, "Endpoint not found")

    def send_file(self, filename, content_type):
        filepath = os.path.join(BASE_DIR, filename)
        if not os.path.exists(filepath):
            self.send_error(404, f"File {filename} not found")
            return
        with open(filepath, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def handle_parse_ubl(self):
        """UBL XML faturasını ayrıştırır ve verileri döner."""
        length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(length)
        try:
            # Hem ham XML hem de JSON { "xml": "..." } destekle
            content = post_data.decode("utf-8", errors="replace")
            if content.strip().startswith("{"):
                try:
                    j = json.loads(content)
                    content = j.get("xml", "")
                except Exception:
                    pass

            parsed = parse_ubl_xml(content)
            self.send_json({"status": "success", "data": parsed})
        except Exception as e:
            self.send_json({"status": "error", "message": str(e)}, status=400)

    def handle_validate_kep(self):
        """KEP adresinin BTK standartlarına uygunluğunu ve sağlayıcısını denetler."""
        length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(length)
        try:
            data = json.loads(post_data.decode("utf-8"))
            kep = data.get("kep_address", "")
            result = validate_kep_address(kep)
            self.send_json(result)
        except Exception as e:
            self.send_json({"valid": False, "message": str(e)}, status=400)

    def handle_calculate_deadline(self):
        """TTK 18/3 8 günlük süre hesabını döner."""
        length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(length)
        try:
            data = json.loads(post_data.decode("utf-8"))
            rec_date = data.get("received_date", "")
            result = calculate_ttk_deadline(rec_date)
            self.send_json(result)
        except Exception as e:
            self.send_json({"valid": False, "message": str(e)}, status=400)

    def handle_create_itiraz(self):
        length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(length)
        try:
            data = json.loads(post_data.decode("utf-8"))
            tracking_code = data.get("tracking_code") or f"ITIRAZ-2026-{random.randint(1000, 9999)}"

            # Süre hesaplama
            rec_date = data.get("received_date", "")
            deadline_info = calculate_ttk_deadline(rec_date) if rec_date else {}
            deadline_date = deadline_info.get("deadline_date", "")

            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO invoice_objections (
                    tracking_code, invoice_number, invoice_uuid, invoice_date, received_date,
                    deadline_date, invoice_amount, seller_title, seller_vkn, seller_kep,
                    buyer_title, buyer_vkn, authorized_person, contact_info,
                    buyer_kep, reason_category, notification_channel,
                    evidence_type, evidence_barcode,
                    detailed_reason, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tracking_code,
                data.get("invoice_number", ""),
                data.get("invoice_uuid", ""),
                data.get("invoice_date", ""),
                rec_date,
                deadline_date,
                float(data.get("invoice_amount", 0)),
                data.get("seller_title", ""),
                data.get("seller_vkn", ""),
                data.get("seller_kep", ""),
                data.get("buyer_title", ""),
                data.get("buyer_vkn", ""),
                data.get("authorized_person", ""),
                data.get("contact_info", ""),
                data.get("buyer_kep", ""),
                data.get("reason_category", ""),
                data.get("notification_channel", ""),
                data.get("evidence_type", ""),
                data.get("evidence_barcode", ""),
                data.get("detailed_reason", ""),
                data.get("status", "İtiraz Gönderildi (KEP/Noter)"),
                data.get("created_at", "")
            ))
            conn.commit()
            conn.close()

            self.send_json({
                "status": "success",
                "tracking_code": tracking_code,
                "deadline_date": deadline_date,
                "remaining_days": deadline_info.get("remaining_days", 8)
            })
        except Exception as e:
            self.send_json({"status": "error", "message": str(e)}, status=500)

    def handle_get_itirazlar(self):
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM invoice_objections ORDER BY id DESC")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()

            # Dinamik güncel kalan süreleri hesapla
            for row in rows:
                if row.get("received_date"):
                    calc = calculate_ttk_deadline(row["received_date"])
                    row["deadline_calc"] = calc
                else:
                    row["deadline_calc"] = {}

            self.send_json(rows)
        except Exception as e:
            self.send_json({"status": "error", "message": str(e)}, status=500)

    def handle_update_status(self):
        length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(length)
        try:
            data = json.loads(post_data.decode("utf-8"))
            tracking_code = data.get("tracking_code")
            new_status = data.get("status")
            evidence_barcode = data.get("evidence_barcode")

            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            if evidence_barcode:
                cur.execute("""
                    UPDATE invoice_objections
                    SET status = COALESCE(?, status), evidence_barcode = ?
                    WHERE tracking_code = ?
                """, (new_status, evidence_barcode, tracking_code))
            else:
                cur.execute("UPDATE invoice_objections SET status = ? WHERE tracking_code = ?", (new_status, tracking_code))
            conn.commit()
            conn.close()

            self.send_json({"status": "success", "updated": tracking_code, "new_status": new_status})
        except Exception as e:
            self.send_json({"status": "error", "message": str(e)}, status=500)

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", PORT))
    print(f"🚀 E-Fatura Itiraz Portali Baslatildi: http://localhost:{port}")
    print(f"⚖️ Yonetim Paneli: http://localhost:{port}/admin")
    with socketserver.TCPServer(("", port), ObjectionHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nSunucu kapatildi.")
