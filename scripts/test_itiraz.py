import unittest
import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server

class TestInvoiceObjectionSystem(unittest.TestCase):
    def setUp(self):
        server.init_db()
        self.conn = sqlite3.connect(server.DB_FILE)
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.cursor()
        cur.execute("DELETE FROM invoice_objections WHERE tracking_code LIKE 'ITIRAZ-TEST%'")
        self.conn.commit()

    def tearDown(self):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM invoice_objections WHERE tracking_code LIKE 'ITIRAZ-TEST%'")
        self.conn.commit()
        self.conn.close()

    def test_database_table_exists(self):
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='invoice_objections'")
        row = cur.fetchone()
        self.assertIsNotNone(row, "invoice_objections tablosu oluşturulmuş olmalıdır.")

    def test_objection_insert_and_retrieve(self):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO invoice_objections (
                tracking_code, invoice_number, invoice_date, received_date,
                invoice_amount, seller_title, seller_vkn, seller_kep,
                buyer_title, buyer_vkn, authorized_person, contact_info,
                buyer_kep, reason_category, notification_channel,
                detailed_reason, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "ITIRAZ-TEST-001",
            "GIB2026000000001",
            "2026-09-18",
            "2026-09-19",
            125000.50,
            "ABC Tedarik A.Ş.",
            "1234567890",
            "abc@hs01.kep.tr",
            "XYZ Sanayi Ltd. Şti.",
            "9876543210",
            "Mehmet Yılmaz",
            "02123456789",
            "xyz@hs02.kep.tr",
            "Sipariş / Sözleşme Dışı Mal ve Hizmet",
            "KEP (Kayıtlı Elektronik Posta)",
            "Sözleşmeye aykırı kesilmiş tutar.",
            "İtiraz Gönderildi (KEP/Noter)",
            "2026-09-20T10:00:00Z"
        ))
        self.conn.commit()

        cur.execute("SELECT * FROM invoice_objections WHERE tracking_code = 'ITIRAZ-TEST-001'")
        record = cur.fetchone()
        self.assertIsNotNone(record)
        self.assertEqual(record["invoice_number"], "GIB2026000000001")
        self.assertEqual(record["seller_vkn"], "1234567890")
        self.assertEqual(record["invoice_amount"], 125000.50)

    def test_status_update(self):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO invoice_objections (tracking_code, invoice_number, status)
            VALUES (?, ?, ?)
        """, ("ITIRAZ-TEST-002", "GIB2026000000002", "Cevap Bekleniyor"))
        self.conn.commit()

        cur.execute("UPDATE invoice_objections SET status = ? WHERE tracking_code = ?", ("Kabul Edildi (İptal/İade Alındı)", "ITIRAZ-TEST-002"))
        self.conn.commit()

        cur.execute("SELECT status FROM invoice_objections WHERE tracking_code = 'ITIRAZ-TEST-002'")
        updated_status = cur.fetchone()[0]
        self.assertEqual(updated_status, "Kabul Edildi (İptal/İade Alındı)")

    def test_files_exist(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(os.path.exists(os.path.join(base_dir, "index.html")), "index.html bulunamadı")
        self.assertTrue(os.path.exists(os.path.join(base_dir, "admin.html")), "admin.html bulunamadı")
        self.assertTrue(os.path.exists(os.path.join(base_dir, "api.php")), "api.php bulunamadı")

if __name__ == "__main__":
    unittest.main()
