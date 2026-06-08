# Metric Dictionary

Bu doküman, İSKİ risk önceliklendirme çalışmasında dashboard ve raporlarda
görünen ana metrikleri tek yerde açıklar. Skorlar saha kararı yerine geçmez;
mahalleleri denetim, bakım ve yenileme için önceliklendirme sinyali olarak
okunmalıdır.

## Temel Birim

| Alan | Tanım |
| --- | --- |
| `ilce` | Standartlaştırılmış ilçe adı |
| `mahalle` | Standartlaştırılmış mahalle adı |
| `anahtar` | `ilce|mahalle` formatında canonical join anahtarı |
| `yil` | Kaynak ölçüm yılı |

## PoF - Probability of Failure

PoF altyapı arızası olasılığını temsil eden 0-1 aralığında normalize edilmiş
proxy skordur. Senaryo 11'de aşağıdaki sinyaller ağırlıklandırılır:

| Sinyal | Yorum |
| --- | --- |
| `ariza_sayisi` | Ham arıza adedi |
| `ariza_yogunlugu` | Nüfusa göre arıza yoğunluğu |
| `komsu_ort_ariza` | Komşu mahallelerdeki arıza baskısı |
| `ort_kesinti_suresi` | Arıza başına ortalama kesinti süresi |
| `ariza_trend` | Yıllar arası kötüleşme/iyileşme sinyali |
| `nufus_basi_tuketim` | Kişi başı tüketim kaynaklı altyapı baskısı |

## CoF - Consequence of Failure

CoF arıza gerçekleştiğinde oluşabilecek etkiyi temsil eden 0-1 aralığında
normalize edilmiş proxy skordur.

| Sinyal | Yorum |
| --- | --- |
| `nufus` | Etkilenebilecek kişi sayısı |
| `sikayet_sayisi` | Vatandaş reaksiyonu ve hizmet kalitesi sinyali |
| `kesinti_suresi_saat` | Toplam kesinti süresi |
| `egitim_tesisi_sayisi` | Hassas kullanıcı etkisi |
| `sanayi_tesis_sayisi` | Ekonomik etki potansiyeli |
| `sikayet_ariza_orani` | Arıza başına şikayet yoğunluğu |
| `komsu_sayisi` | Bağlantılı mahalle etkisi |

## Risk Skoru ve Bant

| Metrik | Tanım |
| --- | --- |
| `S11_PoF_Skor` | Senaryo 11 PoF bileşik skoru |
| `S11_CoF_Skor` | Senaryo 11 CoF bileşik skoru |
| `S11_Risk_Skoru_Surekli` | PoF ve CoF skorlarından türetilen sürekli risk skoru |
| `S11_Risk_Seviyesi` | Dashboard için kullanılan düşük/orta/kritik risk etiketi |

## Harita Join Kalitesi

Harita ekranındaki kapsam tablosu, model çıktısı ile GeoJSON mahalle sınırlarının
canonical `anahtar` üzerinden ne kadar eşleştiğini gösterir.

| Kontrol | Anlamı |
| --- | --- |
| Eşleşen mahalle | Model ve GeoJSON tarafında aynı anahtar var |
| Sadece GeoJSON | Harita sınırında var, model çıktısında yok |
| Sadece model çıktısı | Modelde var, harita sınırında yok |
| Silinen geometri duplikasyonu | Aynı anahtar için birden fazla sınır vardı |
| Filtrelenen harita sınırı | Modelde olmayan sınır harita katmanından çıkarıldı |
