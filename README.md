# 🅿️ Parkwell –  Data driven smart parking system powered by IoT and Big data analytic 

Tim PBL IFC3 MALAM IOT , Yang Beranggotakan: <br>
3312411073 - Bagus Tri Wibowo <br>
3312411087 - Alif rizqullah <br>
3312411045 - Gandhi Mahesa <br>
3312411032 - Ruth Yohana Manurung <br>


<img width="2844" height="1527" alt="Screenshot 2025-07-20 084658" src="https://github.com/user-attachments/assets/a2a8d030-cb71-4396-8886-e7232ac99922" />


Parkwell adalah Aplikasi sistem parkir pintar berbasis web responsive yang memanfaatkan teknologi IoT dan sensor ultrasonic untuk memberikan informasi real-time tentang ketersediaan slot parkir. Pengguna dapat melakukan reservasi langsung melalui perangkat, sehingga menghindari aktivitas berkeliling mencari tempat parkir kosong.

## 🚀 Teknologi yang Digunakan
- Python 3.13.2
- Django
- SQLite (default untuk development)
- Virtual Environment (`.venv`)
- Git & GitHub

---

## 🔧 Cara Clone & Setup Project Ini

Ikuti langkah-langkah berikut untuk mulai bekerja di lokal:

```bash
# 1. Clone repository
https://github.com/bagus564/smartparking.git
cd Parkwell

# 2. Buat virtual environment
python -m venv .venv

# 3. Aktifkan virtual environment
.venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Jalankan migrasi database
python manage.py migrate

# 6. Jalankan development server
python manage.py runserver
```

<b>*Note<b>  

Semua perubahan dilakukan melalui branch develop.  

Setelah fitur stabil, merge ke develop → kemudian akan masuk ke main jika sudah production-ready.
