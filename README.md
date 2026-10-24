# CBT TKA — versi hosting Render + Supabase

Aplikasi latihan CBT berbasis Flask. Mendukung bank soal, admin, paket ujian dengan tautan publik, timer, pengacakan soal, serta penyimpanan hasil.

## Penting
- File ini belum di-deploy. Anda tetap harus mengunggahnya ke GitHub dan membuat layanan Render.
- Untuk hosting Render, gunakan Supabase PostgreSQL melalui variabel `DATABASE_URL`. Jangan mengandalkan SQLite lokal di Render karena disk gratis tidak persisten.
- Pertama kali membuat database, aplikasi membuat tabel dan akun admin dari `ADMIN_USERNAME` serta `ADMIN_PASSWORD`. Atur keduanya sebelum deploy pertama.
- Jika akun admin sudah terbuat, mengganti variabel `ADMIN_PASSWORD` tidak otomatis mengganti hash password akun lama. Jangan menghapus database tanpa membuat backup.
- Bank soal awal merupakan soal latihan buatan, bukan soal resmi/bocoran. Periksa semua soal dan kunci sebelum ujian.
- Tetap uji aplikasi sebelum digunakan untuk ujian penting. Ini bukan sistem ujian berisiko tinggi yang sudah diaudit.

## Variabel Environment di Render
- `SECRET_KEY`: string rahasia acak panjang.
- `ADMIN_USERNAME`: nama login admin yang Anda pilih.
- `ADMIN_PASSWORD`: kata sandi admin kuat.
- `DATABASE_URL`: connection string PostgreSQL dari Supabase (gunakan koneksi Session Pooler jika koneksi Direct tidak dapat dijangkau).

## Render
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Root directory: folder yang berisi `app.py` (kosongkan jika file ada di root repository).

## Supabase
Buat proyek PostgreSQL, buka Connect/Database settings, salin connection string PostgreSQL dan pasang sebagai `DATABASE_URL` di Render. Jangan unggah connection string, password database, atau file `.env` ke GitHub. Simpan cadangan database secara teratur.

## Lokal (opsional)
Python 3.10+:
```bash
pip install -r requirements.txt
python app.py
```
Buka `http://127.0.0.1:5000/admin/login`. Kredensial lokal default hanya untuk pengembangan: `albertttofc` / `albert`. Jangan gunakan default ini pada server publik.
