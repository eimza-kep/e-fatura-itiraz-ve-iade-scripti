# -*- coding: utf-8 -*-
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
    validate_evidence,
    generate_formal_notice_text,
    generate_formal_notice_html,
    export_to_gib_format
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

    def test_formal_notice_text_generation(self):
        sample_data = {
            "tracking_code": "ITIRAZ-TEST-999",
            "invoice_number": "GIB2026000008888",
            "invoice_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "invoice_date": "2026-10-18",
            "received_date": "2026-10-19",
            "invoice_amount": 75000.0,
            "seller_title": "Mega Tedarik San. Tic. A.Ş.",
            "seller_vkn": "1234567890",
            "seller_kep": "megatedarik@hs01.kep.tr",
            "buyer_title": "Kuzey Bilişim Çözümleri Ltd. Şti.",
            "buyer_vkn": "9876543210",
            "buyer_kep": "kuzeybilisim@turkkep.hs01.kep.tr",
            "authorized_person": "Av. Canan Demir",
            "contact_info": "0532 111 2233",
            "reason_category": "Yanlış Birim Fiyat veya Tutar Hesaplaması",
            "detailed_reason": "Sözleşmede belirlenen 100 TL birim fiyat yerine faturada 150 TL uygulanmıştır.",
            "notification_channel": "KEP (Kayıtlı Elektronik Posta)",
            "evidence_type": "KEP",
            "evidence_barcode": "KEP-GUID-2026-998877"
        }

        notice_text = generate_formal_notice_text(sample_data)
        self.assertIn("6102 Sayılı TTK m. 18/3 ve m. 21/2", notice_text)
        self.assertIn("GIB2026000008888", notice_text)
        self.assertIn("Mega Tedarik San. Tic. A.Ş.", notice_text)
        self.assertIn("Kuzey Bilişim Çözümleri Ltd. Şti.", notice_text)
        self.assertIn("75.000,00 TL", notice_text)
        self.assertIn("KEP-GUID-2026-998877", notice_text)
        self.assertIn("sekiz (8) gün içinde", notice_text)

    def test_formal_notice_html_generation(self):
        sample_data = {
            "tracking_code": "ITIRAZ-TEST-888",
            "invoice_number": "GIB2026000007777",
            "invoice_uuid": "11111111-2222-3333-4444-555555555555",
            "invoice_date": "2026-10-20",
            "received_date": "2026-10-21",
            "invoice_amount": 18500.50,
            "seller_title": "Anadolu Donanım Ltd.",
            "seller_vkn": "5555555555",
            "buyer_title": "Boğaziçi Lojistik A.Ş.",
            "buyer_vkn": "4444444444",
            "authorized_person": "Hakan Güven",
            "reason_category": "Teslim Edilmeyen / Eksik Mallar",
            "detailed_reason": "İrsaliye ile teslim edilen 10 adet ürün yerine faturada 50 adet faturalanmıştır."
        }

        notice_html = generate_formal_notice_html(sample_data)
        self.assertIn("<!DOCTYPE html>", notice_html)
        self.assertIn("GIB2026000007777", notice_html)
        self.assertIn("Boğaziçi Lojistik A.Ş.", notice_html)
        self.assertIn("Anadolu Donanım Ltd.", notice_html)
        self.assertIn("18.500,50 TL", notice_html)
        self.assertIn("window.print()", notice_html)
        self.assertIn("TTK 18/3", notice_html)

    def test_gib_export_structure(self):
        sample_records = [
            {
                "tracking_code": "ITIRAZ-TEST-101",
                "invoice_number": "GIB2026000000101",
                "invoice_uuid": "aaaabbbb-cccc-dddd-eeee-ffff00001111",
                "seller_vkn": "1234567890",
                "seller_title": "Tedarikçi A.Ş.",
                "buyer_vkn": "9876543210",
                "buyer_title": "Müşteri Ltd.",
                "invoice_date": "2026-10-10",
                "received_date": "2026-10-12",
                "invoice_amount": 45000.0,
                "notification_channel": "KEP",
                "evidence_type": "KEP",
                "evidence_barcode": "KEP-DELIL-1234",
                "reason_category": "Mükerrer Fatura",
                "detailed_reason": "Aynı ay içerisinde iki kez fatura kesilmiştir.",
                "status": "İtiraz Edildi",
                "created_at": "2026-10-13T10:00:00"
            }
        ]

        gib_export = export_to_gib_format(sample_records)
        self.assertEqual(gib_export["format_version"], "GIB_EFATURA_IPTAL_ITIRAZ_V1.2")
        self.assertEqual(gib_export["total_count"], 1)
        self.assertTrue(len(gib_export["records"]) == 1)

        rec = gib_export["records"][0]
        self.assertEqual(rec["fatura_no"], "GIB2026000000101")
        self.assertEqual(rec["ettn_uuid"], "aaaabbbb-cccc-dddd-eeee-ffff00001111")
        self.assertEqual(rec["satici_vkn_tckn"], "1234567890")
        self.assertEqual(rec["fatura_tutari"], 45000.0)
        self.assertIn("Süre", rec["ttk_sure_durumu"])

    def test_notice_generation_from_db_record(self):
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
            "ITIRAZ-TEST-777", "GIB2026000007777", "uuid-777", "2026-10-15", "2026-10-16",
            "2026-10-24", 15000.0, "Test Satıcı Ltd.", "1111111111", "satici@hs01.kep.tr",
            "Test Alıcı A.Ş.", "2222222222", "Ahmet Bey", "0555",
            "alici@hs02.kep.tr", "Yanlış Fiyat", "KEP", "KEP", "GUID-777",
            "Fiyat uyuşmazlığı", "İtiraz Gönderildi", "2026-10-17T12:00:00"
        ))
        self.conn.commit()

        cur.execute("SELECT * FROM invoice_objections WHERE tracking_code = 'ITIRAZ-TEST-777'")
        row = dict(cur.fetchone())
        html = generate_formal_notice_html(row)
        self.assertIn("GIB2026000007777", html)
        self.assertIn("Test Satıcı Ltd.", html)
        self.assertIn("Test Alıcı A.Ş.", html)
        self.assertIn("GUID-777", html)

        gib_export = export_to_gib_format([row])
        self.assertEqual(gib_export["records"][0]["fatura_no"], "GIB2026000007777")
        self.assertEqual(gib_export["records"][0]["alici_unvan"], "Test Alıcı A.Ş.")

    def test_files_exist(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(os.path.exists(os.path.join(base_dir, "index.html")), "index.html bulunamadı")
        self.assertTrue(os.path.exists(os.path.join(base_dir, "admin.html")), "admin.html bulunamadı")
        self.assertTrue(os.path.exists(os.path.join(base_dir, "api.php")), "api.php bulunamadı")
        self.assertTrue(os.path.exists(os.path.join(base_dir, "scripts", "ubl_helper.py")), "ubl_helper.py bulunamadı")

if __name__ == "__main__":
    unittest.main()
