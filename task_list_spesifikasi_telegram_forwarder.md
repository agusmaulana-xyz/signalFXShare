# Spesifikasi & Task List Project: Telegram Message Forwarder

## 1. Deskripsi Proyek

Program Python berbasis Telegram (menggunakan **Telethon** / userbot) yang memantau pesan dari daftar source (grup/channel), lalu meneruskannya ke daftar destination. Pemetaan diatur lewat `config.json`, sementara kredensial Telegram disimpan di `.env`.

## 2. Fitur Utama

- [x] **Multi-Source & Multi-Destination**: Beberapa rule masing-masing dapat memiliki banyak source dan destination.
- [x] **Konfigurasi**: Pemetaan JSON dan kredensial `.env`; tersedia perintah CLI untuk memindai dialog.
- [x] **Filter Pesan**: Filter kata kunci, jenis media, dan pesan dari bot.
- [x] **Format & Media**: Forward Telegram mempertahankan isi, caption, entitas teks, media, dan album.
- [x] **Rate Limit**: Delay per destination, hormati `FloodWait`, dan retry terbatas untuk error sementara.

## 3. Checklist Tugas

### Tahap 1: Persiapan & Inisialisasi Environment

- [ ] Registrasi Telegram API (`api_id` dan `api_hash`) via [my.telegram.org](https://my.telegram.org) — perlu dilakukan pemilik akun.
- [x] Inisialisasi repository Git dan virtual environment (`.venv`).
- [x] Instalasi dependensi dari `requirements.txt` ke `.venv`.
- [x] Dependensi awal Telethon dan python-dotenv dicatat di `requirements.txt`.
- [x] File konfigurasi dasar `.env.example` dan `config.json`.

### Tahap 2: Autentikasi & Utilitas Telegram

- [x] Buat skrip login Telegram client (user session) dengan input kode dan password 2FA.
- [x] Buat scanner untuk mendapatkan ID/username dialog grup & channel.
- [x] Tampilkan daftar grup/channel ke console agar ID dapat dicatat.

### Tahap 3: Logika Core Forwarder

- [x] Buat event handler untuk pesan baru dari source yang dikonfigurasi.
- [x] Tangani album sebagai satu kelompok dan forward ke setiap destination.
- [x] Terapkan filter pesan opsional dan abaikan pesan outgoing untuk mencegah loop.
- [x] Tangani `FloodWaitError`, delay per destination, dan retry error sementara.

### Tahap 4: Manajemen Konfigurasi (Mapping)

- [x] Buat struktur `config.json` yang fleksibel dengan daftar `rules`.
- [x] Hubungkan modul forwarder dengan pembaca dan validator konfigurasi JSON.

### Tahap 5: Pengujian & Penyempurnaan

- [ ] Uji forward teks melalui Telegram — memerlukan credentials dan grup uji.
- [ ] Uji foto, video, dokumen, dan album melalui Telegram — memerlukan credentials dan grup uji.
- [ ] Uji error koneksi, akses yang dicabut, dan limitasi dari Telegram — memerlukan sesi live.
- [x] Tambahkan unit test lokal untuk validasi konfigurasi dan filter pesan.
- [x] Tambahkan logging ke console dan file berotasi (`logs/forwarder.log`).

## 4. Struktur Folder

```text
PythonShareTele/
├── .env.example
├── .gitignore
├── README.md
├── config.json
├── main.py
├── scanner.py
├── requirements.txt
├── tests/
│   ├── test_config_loader.py
│   └── test_forwarder_filters.py
└── utils/
    ├── config_loader.py
    ├── forwarder.py
    ├── logging_config.py
    ├── settings.py
    └── telegram_client.py
```
