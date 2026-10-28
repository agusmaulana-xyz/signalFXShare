# Telegram Message Forwarder

Forwarder userbot berbasis Telethon. Ia memantau banyak grup/channel dan meneruskan pesan ke satu atau beberapa tujuan sesuai rules di `config.json`. Pesan diteruskan oleh Telegram agar caption, media, entitas teks, dan atribusi sumber tetap terjaga; album dikirim sebagai satu kelompok.

## Persiapan

1. Pasang Python 3.10 atau lebih baru.
2. Buat API credentials di [my.telegram.org](https://my.telegram.org).
3. Dari folder `PythonShareTele`, siapkan environment dan dependensi:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   Copy-Item .env.example .env
   ```

4. Isi `API_ID` dan `API_HASH` dalam `.env`. `PHONE` boleh diisi dengan format internasional, misalnya `+628...`; bila kosong, nomor telepon akan diminta saat login pertama.
5. Login dan lihat grup/channel yang bisa diakses akun:

   ```powershell
   python main.py scan
   # atau: python scanner.py
   ```

   Masukkan kode login Telegram jika diminta. Password 2FA diminta dengan input tersembunyi. Sesi tersimpan di `sessions/telegram_forwarder.session` agar login tidak perlu diulang.

## Atur pemetaan

Salin ID atau username dari hasil pemindaian ke `config.json`. ID angka lebih disarankan, karena username bisa berubah atau tidak tersedia.

Jika `rules` masih kosong, jalankan `py main.py` untuk membuka wizard terminal. Pilih satu nomor sebagai tujuan, lalu pilih satu atau beberapa nomor sumber dengan koma, misalnya `1,3`. Pilihan akan disimpan ke `config.json` dan forwarder langsung berjalan. Jalankan `py main.py setup` untuk mengubah tujuan atau sumber kemudian.

```json
{
  "rules": [
    {
      "name": "berita-ke-grup",
      "sources": [-1001234567890, "channel_sumber_a"],
      "destinations": [-1009876543210, "grup_tujuan_b"],
      "filters": {
        "keywords": ["breaking", "penting"],
        "keyword_mode": "any",
        "media_types": [],
        "ignore_bots": false
      }
    }
  ],
  "ignore_outgoing": true,
  "rate_limit": {
    "delay_seconds": 1.0,
    "max_attempts": 5,
    "flood_wait_buffer_seconds": 1
  }
}
```

Semua field filter opsional. `keywords` kosong berarti tidak memfilter teks; `keyword_mode` menerima `any` atau `all`. `media_types` kosong berarti semua jenis pesan. Pilihan media: `text`, `photo`, `video`, `document`, `audio`, `other`, atau `media` (semua pesan bermedia). Jika beberapa jenis media dipilih, pesan lolos bila cocok dengan salah satunya. Filter kata kunci dan media diterapkan bersama. Pesan album diteruskan utuh jika lolos filter.

## Jalankan

```powershell
python main.py run
# config alternatif: python main.py run --config config-lain.json
```

Jika tanpa subcommand, `python main.py` juga menjalankan forwarder. Log tampil di console dan disimpan ke `logs/forwarder.log`. `FloodWait` dihormati sesuai durasi dari Telegram sebelum percobaan ulang. Pesan yang dikirim akun forwarder diabaikan secara default agar tujuan yang juga menjadi source tidak membuat loop.

## Catatan keamanan dan batasan

- Jangan commit `.env`, file `*.session`, atau membagikan sesi. File sesi memberikan akses ke akun Telegram.
- Akun harus sudah menjadi anggota source dan memiliki izin mengirim ke destination. Channel atau grup yang membatasi forward dari sumber dapat menolak pengiriman.
- Pengiriman langsung ke Telegram membutuhkan API credentials dan akun yang sudah login. Periksa akses channel/grup terlebih dahulu, lalu mulai dengan satu rule yang kecil.

## Pengujian lokal

Jalankan unit test konfigurasi dan filter pesan dengan:

```powershell
python -m unittest discover -s tests -v
```

Uji end-to-end untuk teks, foto/video/dokumen, album, dan error koneksi memerlukan sesi Telegram serta pengiriman ke grup uji yang Anda kendalikan.
