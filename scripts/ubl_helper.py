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


def generate_formal_notice_text(data):
    """
    6102 sayılı Türk Ticaret Kanunu (TTK) Madde 18/3 ve 21/2 uyarınca
    resmi Fatura İtiraz ve İade İhbarnamesi düz metnini (plain text) üretir.
    KEP iletisi gövdesinde veya Noter ihtarname metninde doğrudan kullanılabilir.
    """
    if not isinstance(data, dict):
        raise ValueError("Geçersiz veri: Sözlük (dict) bekleniyor.")

    now_str = date.today().strftime("%d.%m.%Y")
    inv_no = data.get("invoice_number", "BELİRTİLMEDİ")
    inv_uuid = data.get("invoice_uuid", "BELİRTİLMEDİ")
    inv_date = data.get("invoice_date", "BELİRTİLMEDİ")
    rec_date = data.get("received_date", "BELİRTİLMEDİ")
    amount = data.get("invoice_amount", 0.0)
    try:
        amount_fmt = f"{float(amount):,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        amount_fmt = f"{amount} TL"

    seller_title = data.get("seller_title", "MUHATAP ŞİRKET")
    seller_vkn = data.get("seller_vkn", "-")
    seller_kep = data.get("seller_kep", "Belirtilmedi")

    buyer_title = data.get("buyer_title", "KEŞİDECİ ŞİRKET")
    buyer_vkn = data.get("buyer_vkn", "-")
    buyer_kep = data.get("buyer_kep", "Belirtilmedi")
    buyer_auth = data.get("authorized_person", "Yetkili")
    buyer_contact = data.get("contact_info", "-")

    reason_cat = data.get("reason_category", "Sözleşme ve Hukuka Aykırılık")
    detailed_reason = data.get("detailed_reason", "Fatura konusu mal/hizmet şirketimizce kabul edilmemiştir.")

    channel = data.get("notification_channel", "KEP / Noter")
    evidence_type = data.get("evidence_type", "")
    evidence_barcode = data.get("evidence_barcode", "")
    evidence_info = f"{evidence_type} (Barkod/Ref: {evidence_barcode})" if (evidence_type and evidence_barcode) else "İşbu ihtarname ekinde sunulan yasal gönderi kaydı"

    deadline_info = calculate_ttk_deadline(rec_date) if rec_date != "BELİRTİLMEDİ" else {}
    deadline_date = deadline_info.get("deadline_date", "-")

    text = f"""T.C. NOTERLİĞİNE / KAYITLI ELEKTRONİK POSTA (KEP) İHBARNAMESİ
Tarih: {now_str}
KONU: 6102 Sayılı TTK m. 18/3 ve m. 21/2 Uyarınca Fatura İtirazı ve İade İhtarıdır.

KEŞİDECİ (İTİRAZ EDEN ALICI):
  Ticari Unvan : {buyer_title}
  Vergi Dairesi ve VKN : {buyer_vkn}
  KEP Adresi   : {buyer_kep}
  Yetkili Kişi : {buyer_auth}
  İletişim     : {buyer_contact}

MUHATAP (FATURAYI DÜZENLEYEN SATICI):
  Ticari Unvan : {seller_title}
  Vergi Dairesi ve VKN : {seller_vkn}
  KEP Adresi   : {seller_kep}

İTİRAZA KONU FATURA BİLGİLERİ:
  Fatura Seri ve Sıra No : {inv_no}
  ETTN (Fatura UUID)     : {inv_uuid}
  Fatura Düzenleme Tarihi: {inv_date}
  Tebellüğ / Varış Tarihi: {rec_date}
  TTK 18/3 Son İtiraz Günü: {deadline_date}
  Fatura Toplam Tutarı   : {amount_fmt}
  Bildirim Kanalı / Delil: {channel} - {evidence_info}

İTİRAZ GEREKÇESİ:
  Kategori: {reason_cat}
  Açıklama: {detailed_reason}

HUKUKİ DAYANAK VE İZAHAT:
1. 6102 sayılı Türk Ticaret Kanunu'nun (TTK) 21. maddesinin 2. fıkrası uyarınca; bir fatura alan kimse aldığı tarihten itibaren sekiz (8) gün içinde faturanın içeriği hakkında bir itirazda bulunmamışsa içeriğini kabul etmiş sayılır.
2. Yine aynı Kanun'un 18. maddesinin 3. fıkrası gereğince; tacirler arasında diğer tarafı temerrüde düşürmeye, sözleşmeyi feshe veya faturaya itiraz etmeye yönelik beyanların; noter marifetiyle, taahhütlü mektupla, telgrafla veya güvenli elektronik imza kullanılarak kayıtlı elektronik posta (KEP) sistemi ile yapılması şarttır.
3. Yukarıda bilgileri verilen faturaya ilişkin olarak, faturanın tarafımıza ulaştığı {rec_date} tarihinden itibaren yasal 8 günlük hak düşürücü süre içerisinde işbu ihbarname ile süresinde ve usulüne uygun şekilde İTİRAZ ETMEKTEYİZ.
4. Fatura konusu mal veya hizmet ya hiç teslim alınmamış, ya sipariş/sözleşme şartlarına aykırı tanzim edilmiş, ya da taraflar arasında mutabık kalınmayan tutarları içermektedir. Bu nedenle söz konusu fatura tarafımızca ticari defterlerimize kaydedilmemiş ve borç olarak kesinlikle kabul edilmemiştir.

NETİCE VE TALEP:
Yukarıda arz ve izah edilen yasal nedenlerle;
1. Haksız ve hukuka aykırı olarak düzenlenen {inv_no} numaralı ve {amount_fmt} tutarlı faturaya açıkça ve esastan itiraz ettiğimizi,
2. Söz konusu faturanın GİB e-Fatura İptal/İtiraz Portalı veya muhasebe sisteminiz üzerinden derhal İPTAL edilmesini veya İADE faturasının düzenlenmesini,
3. İtirazımızın yasal delili olarak işbu KEP/Noter kaydının resmi kayıtlarınıza işlenmesini ve faturanın iptal edildiğine dair tarafımıza yazılı/elektronik teyit verilmesini ihtaren bildiririz.

İtiraz Eden (Keşideci)
{buyer_title}
Yetkili: {buyer_auth}
(5070 Sayılı Kanun Uyarınca E-İmza ile İmzalanmıştır / Noter Onaylıdır)
"""
    return text.strip()


def generate_formal_notice_html(data):
    """
    Resmi Fatura İtiraz ve İade İhbarnamesinin A4 formatında,
    mahkeme ve noter sunumuna hazır şık HTML çıktısını üretir.
    """
    text_content = generate_formal_notice_text(data)

    now_str = date.today().strftime("%d.%m.%Y")
    inv_no = data.get("invoice_number", "BELİRTİLMEDİ")
    inv_uuid = data.get("invoice_uuid", "BELİRTİLMEDİ")
    seller_title = data.get("seller_title", "MUHATAP ŞİRKET")
    buyer_title = data.get("buyer_title", "KEŞİDECİ ŞİRKET")
    buyer_auth = data.get("authorized_person", "Şirket Yetkilisi")
    amount = data.get("invoice_amount", 0.0)
    try:
        amount_fmt = f"{float(amount):,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        amount_fmt = f"{amount} TL"

    channel = data.get("notification_channel", "KEP / Noter")
    evidence_type = data.get("evidence_type", "")
    evidence_barcode = data.get("evidence_barcode", "")
    tracking_code = data.get("tracking_code", "ITIRAZ-2026")

    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>TTK 18/3 Fatura İtiraz İhbarnamesi - {inv_no}</title>
    <style>
        @page {{ size: A4; margin: 20mm; }}
        body {{
            font-family: 'Times New Roman', Times, serif;
            color: #111;
            line-height: 1.45;
            background: #fff;
            padding: 30px;
            max-width: 800px;
            margin: 0 auto;
            font-size: 11pt;
        }}
        .header-box {{
            text-align: center;
            border-bottom: 2px solid #000;
            padding-bottom: 12px;
            margin-bottom: 20px;
        }}
        .header-title {{
            font-size: 14pt;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .header-sub {{
            font-size: 10pt;
            margin-top: 4px;
            color: #333;
        }}
        .badge-ref {{
            display: inline-block;
            border: 1px solid #333;
            padding: 3px 8px;
            font-size: 9pt;
            font-weight: bold;
            margin-top: 6px;
        }}
        .meta-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 16px;
        }}
        .meta-table td {{
            padding: 6px 8px;
            vertical-align: top;
            border: 1px solid #ccc;
            font-size: 10pt;
        }}
        .meta-table td.lbl {{
            font-weight: bold;
            background-color: #f7f7f7;
            width: 32%;
        }}
        .section-title {{
            font-size: 11pt;
            font-weight: bold;
            background: #eee;
            padding: 4px 8px;
            margin: 16px 0 8px 0;
            border-left: 4px solid #000;
        }}
        .text-body {{
            text-align: justify;
            margin-bottom: 14px;
            text-indent: 20px;
        }}
        .notice-callout {{
            border: 1px solid #000;
            padding: 10px 14px;
            margin: 14px 0;
            background: #fafafa;
            font-weight: 500;
        }}
        .sign-area {{
            margin-top: 35px;
            display: flex;
            justify-content: space-between;
            page-break-inside: avoid;
        }}
        .sign-box {{
            width: 45%;
            text-align: center;
        }}
        .sign-line {{
            margin-top: 45px;
            border-top: 1px dashed #000;
            padding-top: 5px;
            font-size: 10pt;
        }}
        .footer-note {{
            margin-top: 40px;
            border-top: 1px solid #ccc;
            padding-top: 8px;
            font-size: 8pt;
            color: #555;
            display: flex;
            justify-content: space-between;
        }}
        @media print {{
            body {{ padding: 0; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>

<div class="no-print" style="background: #eff6ff; border: 1px solid #93c5fd; padding: 12px 18px; border-radius: 8px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center; font-family: sans-serif;">
    <div>
        <strong>📄 TTK 18/3 Resmi Fatura İtiraz ve İade İhbarnamesi</strong>
        <p style="font-size: 0.85rem; color: #475569; margin-top: 2px;">Bu belgeyi yazdırabilir, PDF olarak kaydedebilir veya KEP eki olarak iletebilirsiniz.</p>
    </div>
    <button onclick="window.print()" style="background: #2563eb; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; cursor: pointer;">🖨️ İhbarnameyi Yazdır / PDF</button>
</div>

<div class="header-box">
    <div class="header-title">T.C. NOTERLİĞİNE / KAYITLI ELEKTRONİK POSTA (KEP) İHBARNAMESİ</div>
    <div class="header-sub">6102 Sayılı Türk Ticaret Kanunu m. 18/3 ve m. 21/2 Uyarınca Yasal İtiraz ve İade Belgesi</div>
    <div class="badge-ref">TAKİP KODU: {tracking_code} | TARİH: {now_str}</div>
</div>

<div class="section-title">1. TARAFLARIN BİLGİLERİ</div>
<table class="meta-table">
    <tr>
        <td class="lbl">KEŞİDECİ (İTİRAZ EDEN)</td>
        <td><strong>{buyer_title}</strong><br>VKN / TCKN: {data.get('buyer_vkn', '-')}<br>KEP: {data.get('buyer_kep', 'Belirtilmedi')}<br>Yetkili: {buyer_auth} | İletişim: {data.get('contact_info', '-')}</td>
    </tr>
    <tr>
        <td class="lbl">MUHATAP (FATURAYI DÜZENLEYEN)</td>
        <td><strong>{seller_title}</strong><br>VKN: {data.get('seller_vkn', '-')}<br>KEP: {data.get('seller_kep', 'Belirtilmedi')}</td>
    </tr>
</table>

<div class="section-title">2. İTİRAZA KONU FATURA DETAYLARI</div>
<table class="meta-table">
    <tr>
        <td class="lbl">Fatura Seri & Sıra No</td>
        <td><strong>{inv_no}</strong></td>
        <td class="lbl">Fatura Tutarı</td>
        <td><strong>{amount_fmt}</strong></td>
    </tr>
    <tr>
        <td class="lbl">ETTN (Fatura UUID)</td>
        <td colspan="3"><code style="font-size: 9pt;">{inv_uuid}</code></td>
    </tr>
    <tr>
        <td class="lbl">Fatura Düzenleme Tarihi</td>
        <td>{data.get('invoice_date', '-')}</td>
        <td class="lbl">Tebellüğ / Varış Tarihi</td>
        <td>{data.get('received_date', '-')}</td>
    </tr>
    <tr>
        <td class="lbl">Bildirim Yolu & Delil Kaydı</td>
        <td colspan="3">{channel} - {evidence_type} {evidence_barcode}</td>
    </tr>
    <tr>
        <td class="lbl">İtiraz Kategori Başlığı</td>
        <td colspan="3"><strong>{data.get('reason_category', 'Sözleşme / Fiyat Uyuşmazlığı')}</strong></td>
    </tr>
</table>

<div class="section-title">3. İTİRAZ GEREKÇESİ VE HUKUKİ İZAHAT</div>
<p class="text-body">
    Muhatap şirket tarafından düzenlenen yukarıda dökümü yapılan <strong>{inv_no}</strong> numaralı ve <strong>{amount_fmt}</strong> tutarlı fatura, tarafımıza ulaştığı tarihten itibaren <strong>6102 sayılı TTK'nın 18/3 ve 21/2 maddelerinde</strong> düzenlenen sekiz (8) günlük kesin yasal hak düşürücü süre içerisinde incelenmiş olup içeriğine, tutarına ve esasına açıkça itiraz edilmektedir.
</p>

<div class="notice-callout">
    <strong>Ayrıntılı İtiraz Beyanı:</strong><br>
    {data.get('detailed_reason', 'Fatura konusu mal/hizmet şirketimizce kabul edilmemiştir.')}
</div>

<p class="text-body">
    Söz konusu fatura içeriğindeki mal/hizmet ya hiç teslim alınmamış, sipariş ve sözleşme şartlarına aykırı tanzim edilmiş veya mutabakat harici tutar içermektedir. Bu sebeple işbu fatura şirketimiz ticari defterlerine kaydedilmemiş, borç olarak kabul edilmemiş ve GİB nezdinde iade/iptal statüsüne alınmıştır.
</p>

<div class="section-title">4. NETİCE VE TALEP</div>
<p class="text-body">
    Yukarıda arz ve izah edilen yasal nedenlerle; faturanın esastan ve usulden reddedildiğini, muhasebe kayıtlarınızda ve Gelir İdaresi Başkanlığı e-Fatura / e-Arşiv sisteminde derhal İPTAL edilmesini veya İADE faturasının düzenlenmesini, iptal işlemine ilişkin tarafımıza yazılı/KEP ile teyit verilmesini ve aksi halde tüm yasal yollara başvurulacağını ihtaren bildiririz.
</p>

<div class="sign-area">
    <div class="sign-box">
        <strong>İhtar Eden (Keşideci)</strong><br>
        {buyer_title}<br>
        <span style="font-size: 9pt;">Yetkili: {buyer_auth}</span>
        <div class="sign-line">İmza / E-İmza Kaşesi</div>
    </div>
    <div class="sign-box">
        <strong>Tebliğ Eden / Gönderi Onayı</strong><br>
        {channel}<br>
        <span style="font-size: 9pt;">Delil No: {evidence_barcode or tracking_code}</span>
        <div class="sign-line">Mazbata / KEP İleti Barkodu</div>
    </div>
</div>

<div class="footer-note">
    <span>İşbu belge e-Fatura İtiraz ve İade Sistemi tarafından TTK 18/3 uyarınca otomatik tanzim edilmiştir.</span>
    <span>Doğrulama Kodu: {tracking_code}</span>
</div>

</body>
</html>"""
    return html


def export_to_gib_format(objections_list):
    """
    GİB e-Fatura İptal/İtiraz Portalı toplu yükleme formatına
    uygun JSON ve CSV yapısını üretir.
    """
    records = []
    for item in objections_list:
        rec_date = item.get("received_date") or item.get("created_at", "")[:10]
        deadline = calculate_ttk_deadline(rec_date) if rec_date else {}

        records.append({
            "fatura_no": item.get("invoice_number", ""),
            "ettn_uuid": item.get("invoice_uuid", ""),
            "satici_vkn_tckn": item.get("seller_vkn", ""),
            "satici_unvan": item.get("seller_title", ""),
            "alici_vkn_tckn": item.get("buyer_vkn", ""),
            "alici_unvan": item.get("buyer_title", ""),
            "fatura_tarihi": item.get("invoice_date", ""),
            "tebellug_tarihi": rec_date,
            "fatura_tutari": float(item.get("invoice_amount", 0.0)),
            "itiraz_yontemi": item.get("notification_channel", "KEP"),
            "delil_turu": item.get("evidence_type", ""),
            "delil_no_barkod": item.get("evidence_barcode", ""),
            "itiraz_kategorisi": item.get("reason_category", ""),
            "itiraz_aciklamasi": item.get("detailed_reason", ""),
            "takip_kodu": item.get("tracking_code", ""),
            "durum": item.get("status", "İtiraz Edildi"),
            "ttk_sure_durumu": deadline.get("status_label", "Hesaplanamadı"),
            "kayit_tarihi": item.get("created_at", "")
        })

    return {
        "format_version": "GIB_EFATURA_IPTAL_ITIRAZ_V1.2",
        "exported_at": datetime.now().isoformat(),
        "total_count": len(records),
        "records": records
    }

