# E-Fatura İtiraz ve İade Yönetim Portalı

[![CI Test Suite](https://github.com/eimza-kep/e-fatura-itiraz-ve-iade-scripti/actions/workflows/ci.yml/badge.svg)](https://github.com/eimza-kep/e-fatura-itiraz-ve-iade-scripti/actions/workflows/ci.yml)
[![Canlı Demo](https://img.shields.io/badge/Demo-Canl%C4%B1%20Test%20Et-brightgreen.svg)](https://eimza-kep.github.io/e-fatura-itiraz-ve-iade-scripti/)
[![Docker Support](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)](Dockerfile)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://python.org)
[![PHP: 7.4+](https://img.shields.io/badge/PHP-7.4%2B-purple.svg)](https://php.net)

KOBİ'ler, şirketler, mali müşavirler (SMMM) ve hukuk büroları için; Türk Ticaret Kanunu (TTK m. 18/3 ve m. 21/2) ile Vergi Usul Kanunu (VUK) hükümleri çerçevesinde **hatalı veya fahiş e-faturalara karşı 8 günlük yasal itiraz süresini takip eden**, **UBL-TR 2.1 XML faturalarını sürükle-bırak yöntemiyle otomatik ayrıştıran**, **BTK onaylı KEP adreslerini denetleyen** ve resmi **KEP/Noter itiraz mazbatası ve ihtarnamesi üreten** kurumsal itiraz ve iade yönetim yazılımı.

---

## 🎯 Temel Yetenekler

- **⚡ Otomatik UBL-TR 2.1 XML Fatura Ayrıştırma:**
  - E-Fatura veya e-Arşiv XML dosyasını sürükleyip bırakarak Fatura No, Belge UUID (ETTN), Tarih, Ödenecek Tutar, Satıcı/Alıcı VKN-TCKN, Unvan ve KEP adreslerini saniyeler içinde otomatik doldurur.
- **🛡️ BTK Onaylı KEP Adres Doğrulama:**
  - İtiraz formundaki alıcı ve satıcı KEP adreslerinin sözdizimini ve BTK onaylı KEPHS sunucu alan adlarını (`@hs01.kep.tr`, `@hs02.kep.tr`, `@hs03.kep.tr`, TÜRKKEP, TNB KEP, PTT KEP vb.) anlık olarak doğrular.
- **⏳ TTK 18/3 & 21/2 Yasal Süre Geri Sayımı:**
  - Faturanın tebliğ tarihi girildiği anda yasal 8 günlük itiraz süresini ve kalan günleri otomatik hesaplar; 2 gün kaldığında kritik uyarı, süre dolduğunda hukuki süre aşımı alarmı verir.
- **📑 Delil Mazbata ve Barkod Takibi:**
  - KEP Delil İletisi GUID numarası, Noter İşlem/Yevmiye Numarası veya PTT Tebliğ Barkodunu (`RR...TR`) kayıt altına alarak yasal ispat güvencesi sağlar.
- **📄 Resmi TTK 18/3 & 21/2 İtiraz İhbarnamesi Üretici (`/api/itiraz/{kod}/dilekce`):**
  - TTK 18/3 ve 21/2 dayanaklı, delil tespiti maddeleri ve yasal ihtarları içeren, A4 boyutunda mahkeme ve noter standartlarında yazdırılabilir veya PDF olarak saklanabilir kurumsal ihtarname üretir.
- **🏛️ GİB e-Fatura İptal/İtiraz Portalı Toplu Dışa Aktarımı (`/api/export-gib`):**
  - GİB portalı toplu itiraz yükleme standartlarına tam uyumlu JSON ve CSV formatında veri ihracı sağlar.
- **🔍 Takip Kodu ve Fatura No ile Anlık Sorgulama API'si:**
  - Mükelleflerin veya sistemlerin itiraz durumunu, kalan yasal süreyi ve resmi ihbarnamesini anında sorgulayabileceği REST uç noktası (`/api/itiraz/{kod}`).
- **📊 Yönetim Paneli (`/admin`):**
  - İtiraz portföyü, kritik son 2 gün filtrelemesi, finansal toplam tutar takibi, durum güncelleme, tek tıkla ihtarname açma ve GİB portalı uyumlu dışa aktarım.
- **🚀 Sıfır Bağımlılık (Zero-Dependency):**
  - Harici paket gerektirmeyen standart Python kütüphaneleri (`sqlite3`, `xml.etree`, `urllib`).

---

## ⚖️ Hukuki Altyapı ve GİB Portalı Entegrasyonu

### 1. TTK Madde 18/3 ve 21/2 Hükümleri
* **TTK m. 21/2:** *"Bir fatura alan kimse aldığı tarihten itibaren sekiz gün içinde, faturanın içeriği hakkında bir itirazda bulunmamışsa bu içeriği kabul etmiş sayılır."*
* **TTK m. 18/3:** *"Tacirler arasında, diğer tarafı temerrüde düşürmeye, sözleşmeyi feshe, sözleşmeden dönmeye ilişkin ihbarlar veya ihtarlar noter aracılığıyla, taahhütlü mektupla, telgrafla veya güvenli elektronik imza kullanılarak kayıtlı elektronik posta sistemi (KEP) ile yapılır."*

### 2. GİB e-Fatura İptal/İtiraz Portalı İş Akışı
1. **Temel Fatura Senaryosu:** Temel faturalar alıcı tarafından sistem üzerinden doğrudan reddedilemediği için yasal itiraz **KEP, Noter veya GİB e-Fatura İptal/İtiraz Portalı** üzerinden 8 gün içinde bildirilmelidir.
2. **Ticari Fatura Senaryosu:** Ticari faturalarda 8 günlük süre içinde portal veya entegratör üzerinden "Red" yanıtı dönülebilir; süre aşımında ise KEP/Noter ihtarı zorunludur.
3. **Portal Durum Kodları:**
   - `İtiraz Talebi Oluşturuldu`: Muhatabın onayına sunuldu.
   - `Kabul Edildi`: Karşı taraf faturanın iptalini veya iadesini kabul etti.
   - `Reddedildi`: Karşı taraf itirazı reddetti (dava/arabuluculuk aşaması).
   - `Zaman Aşımı`: 8 günlük yasal süre aşıldı.

---

## 🚀 Hızlı Başlangıç

### 1. Windows (Tek Tıkla Çalıştır)
1. Repoyu klonlayın veya zip olarak indirin.
2. `Baslat.bat` dosyasına çift tıklayın.
3. Tarayıcınızda otomatik açılacaktır:
   - İtiraz Portalı: `http://localhost:8085`
   - Yönetim Paneli: `http://localhost:8085/admin`

### 2. Linux & macOS
```bash
git clone https://github.com/eimza-kep/e-fatura-itiraz-ve-iade-scripti.git
cd e-fatura-itiraz-ve-iade-scripti
chmod +x baslat.sh
./baslat.sh
```

### 3. Docker ile Çalıştırma
```bash
docker build -t e-fatura-itiraz .
docker run -d -p 8085:8085 -v $(pwd)/fatura_itirazlar.db:/app/fatura_itirazlar.db e-fatura-itiraz
```

### 4. PHP / Paylaşımlı Hosting
Dosyaları sunucunuzdaki `/itiraz/` dizinine yükleyin. `api.php` otomatik olarak JSON veritabanını yapılandıracaktır.

---

## 🔌 API Uç Noktaları

| Yöntem | Endpoint | Açıklama |
|---|---|---|
| `GET` | `/` veya `/index.html` | Kullanıcı itiraz başvuru ve ihtarname ekranı |
| `GET` | `/admin` | Yönetim ve süre takip paneli |
| `GET` | `/health` | Sunucu sağlık durumu kontrolü |
| `GET` | `/api/itirazlar` | Kayıtlı tüm itirazların listesi ve dinamik TTK süre durumu |
| `GET` | `/api/itiraz/{kod}` | Takip kodu veya fatura no ile tekil itiraz durumu sorgulama |
| `GET` | `/api/itiraz/{kod}/dilekce` | TTK 18/3 resmi A4 itiraz ihbarnamesi ve yazdırma şablonu (HTML) |
| `GET` | `/api/export-gib` | GİB e-Fatura İptal/İtiraz Portalı formatında toplu dışa aktarım (JSON/CSV) |
| `POST` | `/api/itiraz-et` | Yeni itiraz kaydı oluşturma ve resmi takip kodu alma |
| `POST` | `/api/durum-guncelle` | İtiraz durumunu ve delil barkodunu güncelleme |
| `POST` | `/api/generate-notice` | JSON verisinden anlık TTK 18/3 resmi ihtarname metni ve HTML çıktısı üretme |
| `POST` | `/api/parse-ubl` | UBL-TR XML fatura içeriğini ayrıştırma |
| `POST` | `/api/validate-kep` | KEP alan adını ve BTK yetkili sağlayıcısını doğrulama |
| `POST` | `/api/calculate-deadline` | Tebliğ tarihine göre TTK 18/3 8 günlük süre hesabı |

---

## 📊 Mimari ve Dosya Yapısı

```
e-fatura-itiraz-ve-iade-scripti/
├── index.html              # UBL yükleme, KEP kontrolü, itiraz formu ve ihtarname
├── admin.html              # Muhasebe itiraz ve süre takip paneli
├── server.py               # Standalone Python SQLite HTTP REST sunucusu (Port 8085)
├── api.php                 # PHP tabanlı REST backend
├── Dockerfile              # Container dağıtım yapılandırması
├── Baslat.bat              # Windows tek tıkla başlatıcı
├── baslat.sh               # Linux / macOS başlatıcı
├── scripts/
│   ├── ubl_helper.py       # UBL XML parser, KEP validator & TTK 18/3 hesaplayıcı
│   └── test_itiraz.py      # Kapsamlı birim test paketi
├── .github/
│   └── workflows/ci.yml    # GitHub Actions otomatik CI test akışı
└── README.md               # Kapsamlı dokümantasyon ve entegrasyon rehberi
```

---

## 🧪 Birim Testleri Çalıştırma

Test paketini yerelde çalıştırmak için:
```bash
python scripts/test_itiraz.py
```

Test paketi şunları doğrular:
- ✅ SQLite veritabanı şeması ve migration bütünlüğü
- ✅ UBL-TR 2.1 XML faturasından Fatura No, UUID, VKN, Unvan ve Tutar ayrıştırması
- ✅ BTK onaylı KEP adres formatı ve sağlayıcı kontrolü (`hs01`, `hs02`, `hs03`, TÜRKKEP, PTT)
- ✅ TTK 18/3 8 günlük süre geri sayımı (Geçerli / Kritik / Süre Doldu)
- ✅ KEP delil GUID, Noter yevmiye ve PTT barkod doğrulama kuralları

---

## 🌐 E-Dönüşüm Açık Kaynak Ekosistemi

Bu portal, [@eimza-kep](https://github.com/eimza-kep) açık kaynak ekosisteminin fatura denetim ve itiraz bileşenidir. İlgili diğer araçlar:

* 📄 [e-fatura-xml-goruntuleyici](https://github.com/eimza-kep/e-fatura-xml-goruntuleyici) - Gelen e-Fatura ve e-İrsaliye XML dosyalarını ayrıştırma ve KDV tevkifat kontrolü.
* 📨 [kep-adresi-dogrulayici](https://github.com/eimza-kep/kep-adresi-dogrulayici) - TTK 18/3 uyarınca noter ve KEP itiraz adresi sözdizim doğrulama aracı.
* 📊 [muhasebe-excel-sablonlari](https://github.com/eimza-kep/muhasebe-excel-sablonlari) - Tevkifat, Ba-Bs mutabakat ve e-SMM hesaplama tabloları.
* 🏢 [kobi-finans-yonetim-excel-sablonlari](https://github.com/eimza-kep/kobi-finans-yonetim-excel-sablonlari) - KOBİ nakit akışı, vade yaşlandırma ve başabaş analizi.
* 🌟 [awesome-turkiye-e-donusum](https://github.com/eimza-kep/awesome-turkiye-e-donusum) - Türkiye e-Dönüşüm açık kaynak araçları ve kütüphaneleri kürasyonu.

---

## ⚖️ Lisans

Bu proje [MIT Lisansı](LICENSE) kapsamında açık kaynak olarak sunulmuştur.
