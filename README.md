# 🤖 LinkedIn Sync AI Agent (dogukanergin.com)

Doğukan Ergin'in portfolyo sitesi (`dogukanergin.com`) için geliştirilmiş otonom **LinkedIn Sync AI Agent**. 
Bu ajan, LinkedIn profilinizdeki (`/recent-activity/all/`) en son paylaşılan gönderiyi otomatik olarak ayıklar, mükerrer kontrolü yapar ve canlı webhook adresinize (`https://dogukanergin.com/api/linkedin-webhook`) aktarır.

---

## 🌟 Temel Özellikler

- **🛡️ Anti-Bot & Stealth Mode**: Playwright Chromium üzerinde otomasyon tespit bayraklarını maskeleyen stealth özellikleri.
- **🔐 Kolay Oturum Yönetimi**: Tek komutla (`python main.py --login`) interaktif giriş yapıp çerezleri `data/session.json` dosyasına kaydetme veya `.env` üzerinden `LINKEDIN_LI_AT` kullanma desteği.
- **⚡ Akıllı Metin ve Medya Ayrıştırıcı**: Gönderi metnini, kalıcı bağlantısını (canonical URL), tarihini ve hashtag (`#tag`) listesini ayıklar.
- **🔄 Mükerrer Gönderim Engeli (State Manager)**: Yerel `data/last_sync.json` üzerinde son gönderilen içeriği ve URL'yi hafızada tutarak gereksiz webhook isteklerini önler.
- **🌐 Güvenilir Webhook İletimi**: Üstel geri çekilme (exponential backoff) ve otomatik tekrar deneme (retry) mekanizması.
- **⏰ Esnek Çalıştırma Seçenekleri**: 
  - Manuel / Tek Seferlik (`--run-once`)
  - Sürekli Günlük Scheduler (`--schedule`)
  - Test / Kuru Çalıştırma (`--dry-run`)
  - Webhook Bağlantı Testi (`--test-webhook`)
  - GitHub Actions ile 0 maliyetli bulut çalıştırma.

---

## 📁 Proje Dosya Yapısı

```
linkedinAIAgent/
├── .github/
│   └── workflows/
│       └── linkedin_sync.yml     # 24 saatte bir çalışan GitHub Actions Cron Pipeline
├── data/
│   ├── session.json              # Kaydedilen LinkedIn oturumu (otomatik oluşur)
│   ├── last_sync.json            # Son senkronize edilen gönderi hafızası
│   ├── debug_screenshot.png      # Hata durumunda otomatik alınan ekran görüntüsü
│   └── debug_page.html           # Hata durumunda kaydedilen sayfa HTML'i
├── logs/
│   └── agent.log                 # 14 günlük rotasyonlu log dosyası
├── src/
│   ├── __init__.py
│   ├── config.py                 # Pydantic tabanlı .env konfigürasyon yöneticisi
│   ├── extractor.py              # Gönderi, URL, tarih ve hashtag ayrıştırıcı
│   ├── scraper.py                # Playwright Stealth tabanlı LinkedIn kazıyıcı
│   ├── state_manager.py          # Durum ve mükerrer kontrol yöneticisi
│   └── webhook.py                # Webhook fırlatıcı (retry destekli)
├── .env                          # Çevre değişkenleri
├── .env.example                  # Örnek konfigürasyon
├── .gitignore                    # Hassas dosyaları hariç tutma kuralları
├── main.py                       # CLI Giriş Noktası
├── requirements.txt              # Python bağımlılıkları
└── README.md                     # Dokümantasyon
```

---

## 🚀 Hızlı Başlangıç & Kurulum

### 1. Bağımlılıkları Yükleyin

```powershell
# Gerekli paketleri kurun
pip install -r requirements.txt

# Playwright Chromium tarayıcısını indirin
playwright install chromium
```

### 2. Yapılandırma (`.env`)

`.env.example` dosyasını `.env` olarak kopyalayın (hazır olarak oluşturulmuştur):

```env
LINKEDIN_ACTIVITY_URL=https://www.linkedin.com/in/dogukanergin/recent-activity/all/
WEBHOOK_URL=https://dogukanergin.com/api/linkedin-webhook
WEBHOOK_SECRET=your_optional_secret_here
HEADLESS=true
SYNC_SCHEDULE_TIME=09:00
```

### 3. LinkedIn Hesabına Giriş Yapın (1 Seferlik)

Ajanın LinkedIn profilinizin paylaşımlarını görebilmesi için tarayıcı üzerinden 1 kez giriş yapması önerilir:

```powershell
python main.py --login
```
*Açılan Chromium penceresinde LinkedIn hesabınıza giriş yapın. Giriş algılandığında `data/session.json` otomatik kaydedilir ve tarayıcı kapanır.*

---

## 🛠️ Kullanım Komutları

| Komut | Açıklama |
| :--- | :--- |
| `python main.py` veya `python main.py --run-once` | LinkedIn'i kontrol eder, yeni gönderi varsa webhook'a atar ve çıkar. |
| `python main.py --dry-run` | Gönderiyi çeker, ekrana basar fakat webhook **göndermez**. |
| `python main.py --schedule` | Ajanı arka planda sürekli çalıştırır; her gün belirlenen saatte (varsayılan `09:00`) otomatik senkronize eder. |
| `python main.py --force` | Gönderi daha önce senkronize edilmiş olsa dahi zorla webhook fırlatır. |
| `python main.py --test-webhook` | Webhook endpoint'inize test amaçlı sahte bir payload fırlatır. |
| `python main.py --login` | Oturum açma penceresini açar ve çerezleri kaydeder. |
| `python main.py --headless false` | Tarayıcının ne yaptığını görsel olarak izlemek için pencereli modda çalıştırır. |

---

## 📡 Webhook Payload Formatı

Endpoint: `POST https://dogukanergin.com/api/linkedin-webhook`

```json
{
  "content": "Yapay zeka ajanları ile web otomasyonu üzerine yeni çalışmam... #AI #Python #Playwright",
  "url": "https://www.linkedin.com/feed/update/urn:li:activity:7123456789012345678/",
  "date": "1d",
  "hashtags": [
    "AI",
    "Python",
    "Playwright"
  ],
  "synced_at": "2026-09-02T01:25:00.000000+00:00"
}
```

---

## ☁️ GitHub Actions ile 0 Maliyetli Otonom Çalıştırma

Projede `.github/workflows/linkedin_sync.yml` hazır bulunmaktadır. GitHub Actions üzerinden her gün otomatik çalışması için:

1. Deponuzu GitHub'a yükleyin.
2. GitHub Repo > **Settings** > **Secrets and variables** > **Actions** bölümüne gidin.
3. Aşağıdaki Secret'ları ekleyin:
   - `LINKEDIN_SESSION_JSON`: `data/session.json` dosyanızın tüm içeriği
   - *(veya)* `LINKEDIN_LI_AT`: LinkedIn tarayıcı çerezlerinizdeki `li_at` değeri
   - `WEBHOOK_SECRET`: Varsa webhook doğrulama tokenınız.
4. Artık GitHub Actions her gün belirlenen saatte sunucu masrafı olmadan ajanı otonom olarak çalıştıracaktır!
