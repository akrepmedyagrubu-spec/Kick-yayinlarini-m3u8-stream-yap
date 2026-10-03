# Kick HLS Relay

Kick kanalının canlı yayınını FFmpeg ile HLS'e dönüştürür ve sabit bir adres sunar:

```
https://SERVISIN.onrender.com/live/index.m3u8
```

## Render'a kurulum

1. Bu klasörü GitHub'da yeni bir repository'ye yükle.
2. Render'da **New → Blueprint** seçip repository'yi bağla. `render.yaml` Docker web servisini ve rastgele `ADMIN_TOKEN` değerini oluşturur.
3. Render servisinin **Environment** bölümünden `ADMIN_TOKEN` değerini kopyala. Güçlü ve gizli tut; bu token yayını başlatıp durdurmaya izin verir.
4. Servis açılınca `https://SERVISIN.onrender.com` adresine git, Kick kanal URL'sini ve tokenı girip **Yayını başlat**'a bas.
5. Oluşan sabit `/live/index.m3u8` adresini HLS oynatıcında kullan.

Servis Docker imajında FFmpeg ve yt-dlp'yi kurar. Render'ın `PORT` değişkenini ve `0.0.0.0` adresini kullanır. HLS dosyaları geçici `/tmp` alanına yazılır; yeniden dağıtım veya yeniden başlatma sırasında yayın kesilir ve panelden tekrar başlatılmalıdır. Sürekli yayın için ücretli, uyumayan bir Render web servisi seç; ücretsiz servis uykuya geçebilir. Çıkış trafiği ve FFmpeg kaynak tüketimi kullandığın Render planına bağlıdır.

## Yerel çalıştırma

Docker ile:

```sh
docker build -t kick-hls-relay .
docker run --rm -p 10000:10000 -e ADMIN_TOKEN='en-az-16-karakterlik-gizli-token' kick-hls-relay
```

Sonra `http://localhost:10000` adresini aç.

## Bilinen sınırlar

- Yalnızca herkese açık Kick kanal URL'leri desteklenir. Kanal canlı olmalı ve yt-dlp tarafından çözümlenebilmelidir.
- Kick'in web/API değişiklikleri yt-dlp desteğini geçici olarak bozabilir; böyle bir durumda yt-dlp güncellemesi gerekebilir.
- Uygulama yayın kaydetmez. Her başlatmada güncel kaynak adresini çözümler ve FFmpeg üzerinden HLS segmentleri üretir.
- Yayını yeniden yayınlamak için gerekli haklara sahip olduğundan emin ol.
