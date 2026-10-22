import unittest
import os
import sys
import sqlite3
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server
from scripts.ubl_helper import (
    parse_ubl_xml,
    validate_kep_address,
    calculate_ttk_deadline,
    validate_evidence
)

SAMPLE_UBL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
    <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
    <cbc:CustomizationID>TR1.2</cbc:CustomizationID>
    <cbc:ProfileID>TICARIFATURA</cbc:ProfileID>
    <cbc:ID>GIB2026000009988</cbc:ID>
    <cbc:UUID>e81b67f1-79b9-4a0b-8d69-65bfa780d6f2</cbc:UUID>
    <cbc:IssueDate>2026-10-15</cbc:IssueDate>
    <cbc:InvoiceTypeCode>SATIS</cbc:InvoiceTypeCode>
    <cbc:DocumentCurrencyCode>TRY</cbc:DocumentCurrencyCode>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID schemeID="VKN">1234567890</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name>Örnek Tedarikçi Teknolojileri A.Ş.</cbc:Name>
            </cac:PartyName>
            <cac:Contact>
                <cbc:ElectronicMail>tedarikci@hs01.kep.tr</cbc:ElectronicMail>
            </cac:Contact>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID schemeID="VKN">9876543210</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name>Hedef Alıcı Sanayi ve Ticaret Ltd. Şti.</cbc:Name>
            </cac:PartyName>
            <cac:Contact>
                <cbc:ElectronicMail>alici@turkkep.hs01.kep.tr</cbc:ElectronicMail>
            </cac:Contact>
        </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:LegalMonetaryTotal>
        <cbc:LineExtensionAmount currencyID="TRY">50000.00</cbc:LineExtensionAmount>
        <cbc:TaxExclusiveAmount currencyID="TRY">50000.00</cbc:TaxExclusiveAmount>
        <cbc:TaxInclusiveAmount currencyID="TRY">60000.00</cbc:TaxInclusiveAmount>
        <cbc:PayableAmount currencyID="TRY">60000.00</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>
    <cac:InvoiceLine>
        <cbc:ID>1</cbc:ID>
        <cbc:InvoicedQuantity unitCode="C62">10</cbc:InvoicedQuantity>
        <cbc:LineExtensionAmount currencyID="TRY">50000.00</cbc:LineExtensionAmount>
    </cac:InvoiceLine>
</Invoice>
"""

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

    def test_database_columns_migrated(self):
        cur = self.conn.cursor()
        cur.execute("PRAGMA table_info(invoice_objections)")
        cols = [col[1] for col in cur.fetchall()]
        for expected in ["invoice_uuid", "deadline_date", "evidence_type", "evidence_barcode"]:
            self.assertIn(expected, cols, f"Eksik sütun: {expected}")

    def test_objection_insert_and_retrieve_with_evidence(self):
        cur = self.conn.cursor()
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
            "ITIRAZ-TEST-001",
            "GIB2026000000001",
            "e81b67f1-79b9-4a0b-8d69-65bfa780d6f2",
            "2026-09-18",
            "2026-09-19",
            "2026-09-27",
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
            "KEP",
            "KEP-DELIL-2026-789456",
            "Sözleşmeye aykırı kesilmiş tutar.",
            "İtiraz Gönderildi (KEP/Noter)",
            "2026-09-20T10:00:00Z"
        ))
        self.conn.commit()

        cur.execute("SELECT * FROM invoice_objections WHERE tracking_code = 'ITIRAZ-TEST-001'")
        record = cur.fetchone()
        self.assertIsNotNone(record)
        self.assertEqual(record["invoice_number"], "GIB2026000000001")
        self.assertEqual(record["invoice_uuid"], "e81b67f1-79b9-4a0b-8d69-65bfa780d6f2")
        self.assertEqual(record["seller_vkn"], "1234567890")
        self.assertEqual(record["invoice_amount"], 125000.50)
        self.assertEqual(record["evidence_type"], "KEP")
        self.assertEqual(record["evidence_barcode"], "KEP-DELIL-2026-789456")

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

    def test_ubl_xml_parsing(self):
        res = parse_ubl_xml(SAMPLE_UBL_XML)
        self.assertEqual(res["invoice_number"], "GIB2026000009988")
        self.assertEqual(res["uuid"], "e81b67f1-79b9-4a0b-8d69-65bfa780d6f2")
        self.assertEqual(res["issue_date"], "2026-10-15")
        self.assertEqual(res["payable_amount"], 60000.00)
        self.assertEqual(res["seller_vkn"], "1234567890")
        self.assertEqual(res["seller_title"], "Örnek Tedarikçi Teknolojileri A.Ş.")
        self.assertEqual(res["seller_kep"], "tedarikci@hs01.kep.tr")
        self.assertEqual(res["buyer_vkn"], "9876543210")
        self.assertEqual(res["buyer_title"], "Hedef Alıcı Sanayi ve Ticaret Ltd. Şti.")
        self.assertEqual(res["buyer_kep"], "alici@turkkep.hs01.kep.tr")
        self.assertEqual(res["line_count"], 1)

    def test_kep_validation(self):
        # Geçerli BTK adresleri
        val1 = validate_kep_address("sirket@hs01.kep.tr")
        self.assertTrue(val1["valid"])
        self.assertIn("hs01", val1["provider"])

        val2 = validate_kep_address("muhasebe@turkkep.hs01.kep.tr")
        self.assertTrue(val2["valid"])
        self.assertIn("TÜRKKEP", val2["provider"])

        val3 = validate_kep_address("info@pttkep.hs01.kep.tr")
        self.assertTrue(val3["valid"])
        self.assertIn("PTT", val3["provider"])

        # Geçersiz adresler
        self.assertFalse(validate_kep_address("sirket@gmail.com")["valid"])
        self.assertFalse(validate_kep_address("invalid-email")["valid"])
        self.assertFalse(validate_kep_address("")["valid"])

    def test_ttk_deadline_calculation(self):
        today = date(2026, 10, 22)
        # 3 gün önce tebliğ edilmiş: 8 - 3 = 5 gün kaldı -> geçerli
        r1 = calculate_ttk_deadline("2026-10-19", reference_date=today)
        self.assertTrue(r1["valid"])
        self.assertEqual(r1["deadline_date"], "2026-10-27")
        self.assertEqual(r1["remaining_days"], 5)
        self.assertEqual(r1["status"], "valid")

        # 7 gün önce tebliğ edilmiş: 1 gün kaldı -> kritik
        r2 = calculate_ttk_deadline("2026-10-15", reference_date=today)
        self.assertTrue(r2["valid"])
        self.assertEqual(r2["remaining_days"], 1)
        self.assertEqual(r2["status"], "critical")

        # 10 gün önce tebliğ edilmiş: -2 gün -> süre doldu
        r3 = calculate_ttk_deadline("2026-10-12", reference_date=today)
        self.assertTrue(r3["valid"])
        self.assertFalse(r3["is_legal"])
        self.assertEqual(r3["status"], "expired")

    def test_evidence_validation(self):
        # KEP Delil GUID
        ev_kep = validate_evidence("KEP", "KEP-DELIL-2026-ABCD-1234")
        self.assertTrue(ev_kep["valid"])

        # Noter Yevmiye No
        ev_noter = validate_evidence("NOTER", "2026/18452")
        self.assertTrue(ev_noter["valid"])

        # PTT Barkod
        ev_ptt = validate_evidence("PTT", "RR123456789TR")
        self.assertTrue(ev_ptt["valid"])

        # Boş barkod
        self.assertFalse(validate_evidence("KEP", "")["valid"])

    def test_files_exist(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(os.path.exists(os.path.join(base_dir, "index.html")), "index.html bulunamadı")
        self.assertTrue(os.path.exists(os.path.join(base_dir, "admin.html")), "admin.html bulunamadı")
        self.assertTrue(os.path.exists(os.path.join(base_dir, "api.php")), "api.php bulunamadı")
        self.assertTrue(os.path.exists(os.path.join(base_dir, "scripts", "ubl_helper.py")), "ubl_helper.py bulunamadı")

if __name__ == "__main__":
    unittest.main()
