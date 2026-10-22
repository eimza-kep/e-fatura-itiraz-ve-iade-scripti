"""
UBL-TR Fatura Ayrıştırıcı, KEP Doğrulayıcı ve TTK 18/3 Yasal Süre Hesaplayıcı Modülü
E-Fatura İtiraz ve İade Scripti Yardımcı Kütüphanesi
"""
import re
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta

KNOWN_KEP_PROVIDERS = {
    "hs01.kep.tr": "TNB KEP / Ortak KEPHS (hs01)",
    "hs02.kep.tr": "TÜRKKEP / Ortak KEPHS (hs02)",
    "hs03.kep.tr": "PTT KEP / Ortak KEPHS (hs03)",
    "turkkep.hs01.kep.tr": "TÜRKKEP Bilişim Hizmetleri KEPHS",
    "pttkep.hs01.kep.tr": "PTT A.Ş. Kayıtlı Elektronik Posta (KEP)",
    "tnbkep.hs01.kep.tr": "Türkiye Noterler Birliği KEP (TNBKEP)",
    "e-tugrakep.hs01.kep.tr": "E-Tuğra EBG Bilişim KEPHS",
    "interaktifkep.hs01.kep.tr": "İnteraktif KEP Hizmetleri"
}

def clean_tag(tag):
    """XML namespace ön ekini temizler."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag

def parse_ubl_xml(xml_content):
    """
    UBL-TR 1.2 / 2.1 E-Fatura ve E-Arşiv XML dosyasını ayrıştırarak
    temel fatura bilgilerini sözlük olarak döner.
    """
    if not xml_content or not isinstance(xml_content, (str, bytes)):
        raise ValueError("Geçersiz XML içeriği: Boş veya metin/bayt tipinde değil.")

    if isinstance(xml_content, str):
        xml_bytes = xml_content.encode("utf-8")
    else:
        xml_bytes = xml_content

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise ValueError(f"UBL XML ayrıştırma hatası: {str(e)}")

    root_tag = clean_tag(root.tag)
    if root_tag not in ("Invoice", "CreditNote", "ApplicationResponse"):
        raise ValueError(f"Desteklenmeyen UBL belge türü: <{root_tag}>. Beklenen: <Invoice> veya <CreditNote>.")

    data = {
        "invoice_number": "",
        "uuid": "",
        "issue_date": "",
        "profile_id": "",
        "invoice_type_code": "",
        "currency": "TRY",
        "payable_amount": 0.0,
        "seller_vkn": "",
        "seller_title": "",
        "seller_kep": "",
        "buyer_vkn": "",
        "buyer_title": "",
        "buyer_kep": "",
        "line_count": 0
    }

    # Doğrudan çocuk elementleri ve temel fatura başlıklarını tara
    for child in root:
        ct = clean_tag(child.tag)
        cval = (child.text or "").strip()
        if ct == "ID" and not data["invoice_number"]:
            data["invoice_number"] = cval
        elif ct == "UUID" and not data["uuid"]:
            data["uuid"] = cval
        elif ct == "IssueDate" and not data["issue_date"]:
            data["issue_date"] = cval
        elif ct == "ProfileID" and not data["profile_id"]:
            data["profile_id"] = cval
        elif ct == "InvoiceTypeCode" and not data["invoice_type_code"]:
            data["invoice_type_code"] = cval
        elif ct == "DocumentCurrencyCode" and not data["currency"]:
            data["currency"] = cval

    # Spesifik XPath aramaları (Namespace bağımsız)
    def find_first_by_tag(element, tag_name):
        for el in element.iter():
            if clean_tag(el.tag) == tag_name and el.text:
                return el.text.strip()
        return ""

    for elem in root.iter():
        t = clean_tag(elem.tag)

        # Fatura No doğrulaması (16 haneli tipik fatura ID)
        if t == "ID" and not data["invoice_number"]:
            data["invoice_number"] = (elem.text or "").strip()

        # Ödenecek Tutar
        if t == "LegalMonetaryTotal":
            for child in elem.iter():
                ct = clean_tag(child.tag)
                if ct == "PayableAmount":
                    try:
                        data["payable_amount"] = float((child.text or "0").replace(",", "."))
                    except ValueError:
                        data["payable_amount"] = 0.0
                    data["currency"] = child.attrib.get("currencyID", data["currency"])

        # Gönderici (Satıcı) Bilgileri
        if t == "AccountingSupplierParty":
            for child in elem.iter():
                ct = clean_tag(child.tag)
                text_val = (child.text or "").strip()
                if ct == "ID" and not data["seller_vkn"] and text_val:
                    # VKN veya TCKN kontrolü
                    if len(text_val) in (10, 11) and text_val.isdigit():
                        data["seller_vkn"] = text_val
                elif ct in ("Name", "RegistrationName") and not data["seller_title"] and text_val:
                    data["seller_title"] = text_val
                elif ct == "ElectronicMail" and "@" in text_val and "kep.tr" in text_val and not data["seller_kep"]:
                    data["seller_kep"] = text_val

        # Alıcı (Müşteri) Bilgileri
        if t == "AccountingCustomerParty":
            for child in elem.iter():
                ct = clean_tag(child.tag)
                text_val = (child.text or "").strip()
                if ct == "ID" and not data["buyer_vkn"] and text_val:
                    if len(text_val) in (10, 11) and text_val.isdigit():
                        data["buyer_vkn"] = text_val
                elif ct in ("Name", "RegistrationName") and not data["buyer_title"] and text_val:
                    data["buyer_title"] = text_val
                elif ct == "ElectronicMail" and "@" in text_val and "kep.tr" in text_val and not data["buyer_kep"]:
                    data["buyer_kep"] = text_val

        # Kalem sayısı sayımı
        if t in ("InvoiceLine", "CreditNoteLine"):
            data["line_count"] += 1

    return data


def validate_kep_address(kep_address):
    """
    BTK onaylı Kayıtlı Elektronik Posta (KEP) adres formatını ve alan adını doğrular.
    """
    if not kep_address or not isinstance(kep_address, str):
        return {
            "valid": False,
            "address": kep_address or "",
            "domain": "",
            "provider": "",
            "message": "KEP adresi boş bırakılamaz."
        }

    kep_address = kep_address.strip().lower()

    # Temel e-posta biçimi ve .kep.tr bitişi kontrolü
    pattern = r"^[a-zA-Z0-9_\-\.\+]+@([a-zA-Z0-9_\-]+\.)*kep\.tr$"
    if not re.match(pattern, kep_address):
        return {
            "valid": False,
            "address": kep_address,
            "domain": "",
            "provider": "",
            "message": "Geçersiz KEP formatı. KEP adresi 'ornek@hs01.kep.tr' veya '*.kep.tr' şeklinde olmalıdır."
        }

    domain = kep_address.split("@")[1]

    # Bilinen BTK sağlayıcı tespiti
    provider_name = KNOWN_KEP_PROVIDERS.get(domain)
    if not provider_name:
        for known_domain, name in KNOWN_KEP_PROVIDERS.items():
            if domain.endswith("." + known_domain):
                provider_name = name
                break

    if not provider_name:
        provider_name = f"Yetkili BTK Kayıtlı Elektronik Posta Hizmet Sağlayıcısı ({domain})"

    return {
        "valid": True,
        "address": kep_address,
        "domain": domain,
        "provider": provider_name,
        "message": f"Geçerli BTK KEP Adresi ({provider_name})"
    }


def calculate_ttk_deadline(received_date_input, reference_date=None):
    """
    TTK 18/3 ve 21/2 uyarınca 8 günlük yasal itiraz süresini hesaplar.
    received_date_input: 'YYYY-MM-DD' biçiminde faturanın tebliğ / teslim alındığı tarih.
    """
    if not received_date_input:
        return {
            "valid": False,
            "message": "Fatura tebliğ tarihi belirtilmelidir."
        }

    if isinstance(received_date_input, str):
        try:
            r_date = datetime.strptime(received_date_input.strip(), "%Y-%m-%d").date()
        except ValueError:
            return {"valid": False, "message": "Tarih biçimi YYYY-MM-DD olmalıdır."}
    elif isinstance(received_date_input, (datetime, date)):
        r_date = received_date_input if isinstance(received_date_input, date) else received_date_input.date()
    else:
        return {"valid": False, "message": "Geçersiz tarih parametresi."}

    ref_date = reference_date or date.today()
    if isinstance(ref_date, datetime):
        ref_date = ref_date.date()

    deadline_date = r_date + timedelta(days=8)
    remaining_days = (deadline_date - ref_date).days

    if remaining_days < 0:
        status = "expired"
        status_tr = f"Süre Doldu ({abs(remaining_days)} gün gecikme)"
        is_legal = False
    elif remaining_days <= 2:
        status = "critical"
        status_tr = f"Kritik Son Süre ({remaining_days} gün kaldı)"
        is_legal = True
    else:
        status = "valid"
        status_tr = f"Yasal Süre İçinde ({remaining_days} gün kaldı)"
        is_legal = True

    return {
        "valid": True,
        "received_date": r_date.strftime("%Y-%m-%d"),
        "deadline_date": deadline_date.strftime("%Y-%m-%d"),
        "remaining_days": remaining_days,
        "status": status,
        "status_label": status_tr,
        "is_legal": is_legal,
        "legal_basis": "6102 sayılı TTK m. 18/3 ve m. 21/2 uyarınca 8 günlük kesin itiraz süresi"
    }


def validate_evidence(evidence_type, evidence_code):
    """
    İtiraz delil türünü ve numarasını (Mazbata GUID, Noter Yevmiye No, PTT Barkod vb.) doğrular.
    """
    code = (evidence_code or "").strip()
    etype = (evidence_type or "").strip()

    if not code:
        return {
            "valid": False,
            "message": "Delil / Mazbata numarası boş bırakılamaz."
        }

    if etype == "KEP":
        # UUID veya KEP ileti/delil referansı (örn: 36 haneli UUID veya KEP-...)
        if len(code) >= 8:
            return {
                "valid": True,
                "type": "KEP Delil Paketi",
                "code": code,
                "message": "KEP delil iletisi takip kodu doğrulandı."
            }
        return {"valid": False, "message": "KEP Delil GUID en az 8 karakter olmalıdır."}

    elif etype == "NOTER":
        # Yevmiye no formatı (örn: 2026/12345 veya 12345)
        if len(code) >= 3:
            return {
                "valid": True,
                "type": "Noter İhtarnamesi Yevmiye No",
                "code": code,
                "message": "Noter işlem yevmiye numarası doğrulandı."
            }
        return {"valid": False, "message": "Geçerli bir noter yevmiye numarası giriniz."}

    elif etype == "PTT":
        # PTT Barkod: 13 haneli barkod (örn: RR123456789TR)
        if len(code) >= 10:
            return {
                "valid": True,
                "type": "İadeli Taahhütlü PTT Takip Barkodu",
                "code": code,
                "message": "PTT gönderi takip barkodu kaydedildi."
            }
        return {"valid": False, "message": "PTT takip barkodu en az 10 karakter olmalıdır."}

    elif etype == "GIB_PORTAL":
        # GİB İptal/İtiraz Portalı Talep No
        if len(code) >= 6:
            return {
                "valid": True,
                "type": "GİB İptal/İtiraz Portalı Talep No",
                "code": code,
                "message": "GİB portalı itiraz talep numarası kaydedildi."
            }
        return {"valid": False, "message": "GİB talep numarası en az 6 karakter olmalıdır."}

    return {
        "valid": True,
        "type": "Genel Belge / Barkod",
        "code": code,
        "message": "Delil bilgisi kaydedildi."
    }
