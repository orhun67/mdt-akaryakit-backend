# MDT Akaryakıt Takip

Türkiye benzin, motorin ve LPG haberlerini toplar; **en az üç bağımsız, incelenmiş
kanıt** aynı yakıt, tutar, durum ve yürürlük zamanını doğruladığında Firestore'a
yazar ve `akaryakit_alerts` FCM konusuna bildirim gönderir.

## Mevcut durum ve sınırlar

- GitHub Actions her saat 17 ve 47. dakikada çalışacak şekilde ayarlanmıştır.
  GitHub zamanlayıcısı gecikebilir; kesintisiz veya anlık hizmet garantisi değildir.
- TRT, NTV ve Dünya RSS akışları haber **adayı** toplamak içindir. Erişim durumları
  her çalışmada `monitor_health/latest` belgesine ve Actions özetine yazılır.
- Başlık/özet, bağımsız kaynak teyidi değildir. Aynı ajans haberi farklı sitelerde
  yayımlanınca üç teyit sayılmaz. Bu nedenle RSS adayları otomatik onaylanmaz.
- Bağımsız kaynak sicili ve incelenmiş kanıt beslemesi kurulmadan sistem tam
  otomatik fiyat doğrulaması yapmaz. Eski `verificationCount: 3` test verisi
  bildirim tetiklemez. Kaynak sorunu “değişiklik yok” olarak gösterilmez.
- Beklenen değişiklik, zamanı geldiği için gerçekleşmiş sayılmaz; yeni gerçekleşme
  kanıtları gerekir. Çelişkili tutarlarda bildirim bloke edilir.
- Android projesi bu depoda yoktur. Telefonun FCM konu aboneliği, foreground
  servisi ve Firestore ekran bağlantısı ayrıca uçtan uca doğrulanmalıdır.

## Veri modeli

`fuel_candidates/{url_hash}`: RSS başlığı, URL, yayımlanma zamanı, yayıncı.

`fuel_source_registry/{originId}`: Yetkili sunucunun denetlediği özgün kaynak
sicili. Alanlar: `enabled` (boolean), `domains` (tam alan adları listesi),
`independenceGroup` (aynı ajans/ortak özgün kaynağa aynı kimlik).
Sadece yayıncı alan adı farklı diye farklı grup atamayın.

`fuel_observations/{id}`: `originId`, `url`, `reviewed: true`, `reviewedBy`,
`fuelId` (`motorin`, `benzin`, `lpg`), `state` (`expected_increase`,
`expected_decrease`, `increase`, `decrease`), `changeTl` (işaretli TL/litre),
`publishedAt` (Firestore Timestamp), `effectiveAt` (saat dilimli ISO veya Timestamp).
Kaynak sayfasındaki gerçek yürürlük zamanı kullanılmalıdır; yayın zamanı değildir.
Üretim kanıtlarını güvenilir bir inceleyici ya da doğrulanmış yapılandırılmış veri
adaptörü sağlamalıdır. Bu depo henüz böyle bir adaptör içermiyor.

`fuel_status/{fuelId}`: Android şeması korunur: `fuelName`, `state`, `changeTl`,
`effectiveAt`, `verificationCount`, `headline`, `sources`, `eventId`, `updatedAt`.

`fuel_alerts/{eventId}`: Kalıcı tekrar engeli. Gönderimden önce atomik kayıt
oluşturulur. Aynı olay yeniden gönderilmez. FCM çağrısı sırasında kesinti olursa
teslimat belirsiz kalabilir; otomatik tekrar yapılmaz. `claimed` ve `uncertain`
kayıtlar incelenmelidir. Bu tercih olası kayıp pahasına tekrarları önler;
uçtan uca tam-bir-kez teslimat garantisi vermez.

## Erişim ve çalıştırma

Mevcut GitHub Actions `FIREBASE_SERVICE_ACCOUNT` sırrı kullanılır; servis anahtarı
kodda veya loglarda yer almamalıdır. Firestore kuralları mobil/web istemcilerin
**tüm sunucu koleksiyonlarına yazmasını engellemelidir**; sadece Admin SDK yazar.
Özellikle kaynak sicili ve kanıt onayını istemciye açmayın. Mevcut Firebase
kuralları bu depodan görülemediği için doğrulanmamıştır.

```sh
python -m unittest discover -s tests -v
pip install -r requirements.txt
python main.py
```

Bildirim kanalı `fuel_alerts`, FCM konusu `akaryakit_alerts`.
Android 13+ bildirim izni gerekir. FCM teslimatı cihaz bağlantısına ve ayarlarına
bağlıdır. Cihazda `eventId` ile ayrıca tekrar engeli uygulanması önerilir.

Arayüz renkleri: 🔴 zam, 🟢 indirim, 🟡 beklenen, ⚪ doğrulanmış değişiklik yok.
Veri yok/bağlantı hatası ayrı gösterilmelidir. Tablo sütunları: yakıt türü, durum,
değişim (TL/L), yürürlük tarihi/saati, teyit durumu, sonuç.
