# Kick HLS Relay

Render servisi açılınca Kick kanal yayını otomatik başlar. Kullanıcı paneli, token veya her açılışta elle başlatma gerekmez.

Sabit HLS adresi:

```
https://SERVISIN.onrender.com/live/index.m3u8
```

## Kurulum

1. Bu klasörü GitHub'da bir repository'ye yükleyin.
2. Render'da **New → Blueprint** ile bu repository'yi bağlayın.
3. Blueprint `KICK_URL` istediğinde `https://kick.com/kanal-adin` biçiminde kanal adresini gir. İstersen servis oluşturulduktan sonra **Environment → KICK_URL** alanına da ekleyebilirsiniz.
4. Deploy tamamlanınca `https://SERVISIN.onrender.com` sayfası durum ve sabit m3u8 adresini gösterir.

Yayın canlı değilse uygulama 20 saniyede bir tekrar dener. Kick kanalını değiştirmek için Render'da `KICK_URL` değerini güncelle; değişiklik servisi yeniden dağıtır ve yeni yayın otomatik başlar.

## Render notları

Servis Docker imajında FFmpeg ve yt-dlp kurar, Render'ın `PORT` değişkenini kullanır ve `0.0.0.0` adresinde dinler. HLS segmentleri geçici dosya alanında tutulur; yeniden dağıtımda veya yeniden başlatmada m3u8 oynatımı kısa süre kesilir, servis tekrar açılınca yayın otomatik başlar. Kesintisiz kullanım için ücretli, uyumayan bir Render web servisi gerekir. Render web servislerinin varsayılan dosya sistemi geçicidir ve ücretsiz servis planının uyku/çalışma sınırları vardır.

## Yerel çalıştırma

```sh
docker build -t kick-hls-relay .
docker run --rm -p 10000:10000 -e KICK_URL='https://kick.com/kanal-adin' kick-hls-relay
```

Tarayıcıda `http://localhost:10000` adresini aç.

Yayın herkese açık bir Kick kanalı olmalı ve yt-dlp tarafından çözümlenebilmelidir. Kick tarafındaki değişiklikler geçici kesintilere neden olabilir. Yayını yeniden aktarmak için gerekli haklara sahip olduğundan emin olunuz.

