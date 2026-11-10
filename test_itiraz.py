# -*- coding: utf-8 -*-
import unittest
from datetime import date, timedelta
from scripts.ubl_helper import (
    validate_kep_address,
    calculate_ttk_deadline,
    get_ttk_deadline_urgency
)

class TestInvoiceObjection(unittest.TestCase):
    def test_kep_validation(self):
        res1 = validate_kep_address("sirket@hs01.kep.tr")
        self.assertTrue(res1["valid"])
        self.assertIn("TNB", res1.get("provider", ""))

        res2 = validate_kep_address("deneme@kolaykep.hs01.kep.tr")
        self.assertTrue(res2["valid"])

        res3 = validate_kep_address("invalid-email")
        self.assertFalse(res3["valid"])

    def test_ttk_deadline_calc(self):
        recv_str = date.today().strftime("%Y-%m-%d")
        dl_res = calculate_ttk_deadline(recv_str)
        self.assertTrue(dl_res["valid"])
        expected_dl = (date.today() + timedelta(days=8)).strftime("%Y-%m-%d")
        self.assertEqual(dl_res["deadline_date"], expected_dl)

    def test_urgency_status(self):
        today = date.today()
        crit = get_ttk_deadline_urgency(str(today + timedelta(days=1)))
        self.assertIn(crit["status"], ["KRITIK", "ACIL"])
        expired = get_ttk_deadline_urgency(str(today - timedelta(days=1)))
        self.assertEqual(expired["status"], "SURESI_DOLDU")

if __name__ == "__main__":
    unittest.main()
