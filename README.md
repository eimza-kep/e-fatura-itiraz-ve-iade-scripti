# E-Fatura İtiraz ve İade Yönetim Portalı

[![CI Test Suite](https://github.com/eimza-kep/e-fatura-itiraz-ve-iade-scripti/actions/workflows/ci.yml/badge.svg)](https://github.com/eimza-kep/e-fatura-itiraz-ve-iade-scripti/actions/workflows/ci.yml)
[![Canlı Demo](https://img.shields.io/badge/Demo-Canl%C4%B1%20Test%20Et-brightgreen.svg)](https://eimza-kep.github.io/e-fatura-itiraz-ve-iade-scripti/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.8+](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg)](https://python.org)
[![PHP: 7.4+](https://img.shields.io/badge/PHP-7.4%2B-purple.svg)](https://php.net)

KOBİ'ler, şirketler, mali müşavirler (SMMM) ve hukuk büroları için; Türk Ticaret Kanunu (TTK m. 18/3 ve 21/2) ile Vergi Usul Kanunu (VUK) hükümleri çerçevesinde **hatalı veya fahiş e-faturalara karşı 8 günlük yasal itiraz süresini takip eden**, resmi **KEP ve Noter İhtarnamesi dilekçesi üreten** kurumsal itiraz ve iade yönetim yazılımı.

---

## 🎯 Temel Yetenekler

- **TTK 18/3 Otomatik Süre Hesaplayıcı:** Faturanın tebliğ tarihi girildiği anda yasal 8 günlük itiraz süresini ve kalan günleri hesaplar, süre aşımı riski durumunda kırmızı alarm verir.
- **Resmi İtiraz Metni Üretici (KEP & Noter Uyumlu):** Yargıtay içtihatları ve TTK 18/3 standartlarına uygun, yazdırılabilir veya PDF olarak kaydedilebilir hukuki itiraz ihtarnamesini tek tıkla üretir.
- **Detaylı İtiraz Sınıflandırması:** Sipariş dışı mal/hizmet, fahiş birim fiyat, teslim edilmeyen ürün, mükerrer kesilen fatura veya sözleşmeye aykırı vade.
- **Muhasebe & Finans Yönetim Paneli (`/admin`):**
  - Tüm itirazların canlı listesi ve kritik süre geri sayımı.
  - Toplam itiraz edilen fatura tutarı analitiği.
  - İtiraz akış takibi: "İtiraz Gönderildi (KEP)", "Cevap Bekleniyor", "Kabul Edildi (İptal/İade)", "Reddedildi".
  - Excel uyumlu UTF-8 BOM destekli tek tıkla **CSV Dışa Aktarımı**.
- **Sıfır Bağımlılık (Zero-Dependency):**
  - **Python Motoru:** Dahili SQLite veritabanı ile tek tıkla lokalde veya sunucuda çalışır (`server.py`).
  - **PHP Motoru:** Paylaşımlı hosting, cPanel ve Plesk için hazır JSON tabanlı backend (`api.php`).
  - **Offline Mod:** Bağlantı kesintilerinde yerel depolama (`localStorage`) desteği.

---

## 🚀 Hızlı Başlangıç

### Windows (Tek Tıkla Çalıştır)
1. Repoyu klonlayın veya indirin.
2. `Baslat.bat` dosyasına çift tıklayın.
3. Otomatik olarak açılır:
   - İtiraz Oluşturma: `http://localhost:8085`
   - Yönetim Paneli: `http://localhost:8085/admin`

### Linux & macOS
```bash
git clone https://github.com/eimza-kep/e-fatura-itiraz-ve-iade-scripti.git
cd e-fatura-itiraz-ve-iade-scripti
chmod +x baslat.sh
./baslat.sh
```

### PHP / Paylaşımlı Hosting
Dosyaları sunucunuzdaki `/itiraz/` veya `/fatura/` dizinine yükleyin. `api.php` otomatik olarak JSON veritabanını yapılandıracaktır.

---

## 📊 Mimari ve Dosya Yapısı

```
e-fatura-itiraz-ve-iade-scripti/
├── index.html              # Fatura itiraz formu ve resmi ihtarname çıktısı
├── admin.html              # Muhasebe itiraz ve süre takip paneli
├── server.py               # Standalone Python SQLite HTTP sunucusu (Port 8085)
├── api.php                 # PHP tabanlı REST backend
├── Baslat.bat              # Windows tek tıkla başlatıcı
├── baslat.sh               # Linux / macOS başlatıcı
├── scripts/
│   └── test_itiraz.py      # Otomatik test paketi
├── .github/
│   └── workflows/ci.yml    # GitHub Actions CI testi
└── README.md               # Dokümantasyon
```

---

## 🧪 Testleri Çalıştırma

```bash
python scripts/test_itiraz.py
```

---

## ⚖️ Lisans

Bu proje [MIT Lisansı](LICENSE) kapsamında açık kaynak olarak sunulmuştur.
