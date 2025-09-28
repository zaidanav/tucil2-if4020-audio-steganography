# Tucil II IF4020 - Audio Steganography

## Nama dan Deskripsi Program

**Audio Steganography dengan Multiple-LSB**

Program steganografi untuk menyembunyikan berkas rahasia (secret message) ke dalam berkas audio digital MP3/WAV menggunakan metode multiple-LSB (Least Significant Bit). Program mendukung enkripsi dengan extended Vigenère cipher (256 karakter) dan penyisipan pada titik acak berdasarkan seed yang diberikan.

## Kumpulan Teknologi yang Digunakan (Tech Stack)

### Bahasa Pemrograman
- **Python 3.10+** - Bahasa pemrograman utama

### Libraries dan Dependencies
- **numpy** - Manipulasi array dan operasi numerik
- **pydub** - Pengolahan dan konversi file audio (MP3/WAV)
- **pygame** - Audio playback untuk preview audio
- **tkinter** - GUI framework (built-in Python)
- **wave** - Encoding file WAV (built-in Python)
- **struct** - Binary data packing/unpacking (built-in Python)
- **hashlib** - Hashing untuk seed generation (built-in Python)

### Tools
- **FFmpeg** - Backend untuk pydub (diperlukan untuk konversi MP3)

## Dependensi

### Instalasi Requirements
```bash
pip install -r requirements.txt
```

### Requirements.txt
```
numpy
pydub
pygame
```

### Instalasi FFmpeg
**Windows:**
- Download dari https://ffmpeg.org/download.html
- Extract dan tambahkan ke PATH

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

## Tata Cara Menjalankan Program

### Metode 1: Menjalankan GUI
```bash
cd src
python -m gui.app
```

### Metode 2: Menggunakan pip install (opsional)
```bash
cd src
pip install -e .
tucil2-stego
```

### Metode 3: Direct execution
```bash
cd src
python gui/app.py
```

## Fitur Utama

### Fitur Penyisipan (Embed)
- ✅ Support file audio MP3 dan WAV (mono/stereo)
- ✅ Multiple-LSB (1-4 bit LSB)
- ✅ Enkripsi dengan extended Vigenère cipher (256 karakter)
- ✅ Penyisipan pada titik acak berdasarkan seed
- ✅ Support sembarang tipe dan ukuran file rahasia
- ✅ Kalkulasi kapasitas sebelum embed
- ✅ Audio playback untuk preview
- ✅ Perhitungan PSNR (Peak Signal-to-Noise Ratio)

### Fitur Ekstraksi (Extract)
- ✅ Auto-detect parameter embed (n-LSB, enkripsi, randomisasi)
- ✅ Dekripsi otomatis jika terenkripsi
- ✅ Restore nama dan ekstensi file asli
- ✅ Audio playback untuk preview stego audio

### Fitur Tambahan
- 🎵 **Audio Playback**: Preview cover dan stego audio
- 📊 **PSNR Calculation**: Mengukur kualitas audio setelah steganografi
- 🔧 **Capacity Analysis**: Analisis kapasitas cover audio
- 💾 **Flexible Output**: Save stego audio dengan nama custom
- 🎛️ **GUI Interface**: Interface yang user-friendly

## Struktur Project
```
src/
├── gui/
│   ├── __init__.py
│   └── app.py              # Main GUI application
├── stego/
│   ├── __init__.py
│   ├── bitops.py           # Bit manipulation utilities
│   ├── capacity.py         # Capacity calculation (MP3 padding)
│   ├── capability_exceptions.py  # Custom exceptions
│   ├── crypto.py           # Vigenère cipher implementation
│   ├── meta.py             # Header metadata handling
│   ├── mp3stream.py        # MP3 frame parsing
│   ├── pipeline.py         # Main embed/extract pipeline
│   ├── player.py           # Audio playback functionality
│   ├── psnr.py             # PSNR calculation
│   ├── reader.py           # Bit extraction from MP3 padding
│   ├── seed.py             # Seed generation utilities
│   └── writer.py           # Bit embedding to MP3 padding
├── pyproject.toml
└── requirements.txt
```

## Penggunaan

### 1. Embed (Penyisipan)
1. Pilih **cover audio** (MP3/WAV)
2. Pilih **secret file** (file apapun yang ingin disembunyikan)
3. Tentukan **output path** untuk stego audio
4. Atur parameter:
   - **n-LSB**: Jumlah bit LSB (1-4)
   - **Encrypt**: Aktifkan enkripsi Vigenère
   - **Random start**: Aktifkan penyisipan acak
   - **Key**: Kunci stego (maksimal 25 karakter)
5. Klik **"Embed"**

### 2. Extract (Ekstraksi)
1. Pilih **stego audio** (hasil dari proses embed)
2. Pilih **output folder** untuk file hasil ekstraksi
3. Masukkan **key** yang sama dengan saat embed
4. Klik **"Extract"**

## Implementasi Kreatif

### 1. Seed Generation
Konversi string key menjadi seed numerik menggunakan SHA-256:
```python
def seed_from_key(key: str) -> int:
    h = hashlib.sha256(key.encode('utf-8')).digest()
    return int.from_bytes(h[:8], 'big', signed=False)
```

### 2. Audio Sample Processing
Program menggunakan PCM samples audio (bukan MP3 padding) untuk steganografi:
- Decode MP3/WAV → PCM samples
- Embed bits pada n-LSB samples
- Encode kembali ke WAV

### 3. Auto-Detection pada Extract
Program mencoba berbagai kombinasi parameter untuk menemukan data tersembunyi:
```python
for n in (1,2,3,4):
    for rnd in (True, False):
        attempt = _try_extract_with_params(samples, key, n_lsb=n, use_rand_start=rnd)
```

### 4. Metadata Storage
Informasi disimpan dalam header custom:
- Magic signature "STEG"
- Flags (encrypted, randomized)
- n-LSB yang digunakan
- Nama dan ekstensi file asli
- Panjang payload

## Catatan Penting

1. **Output Format**: Program selalu mengoutput stego audio dalam format WAV (tidak bisa MP3 karena lossy compression akan merusak data tersembunyi)

2. **PSNR Threshold**: Nilai PSNR minimal 30 dB menandakan kualitas audio yang baik

3. **Key Sensitivity**: Key harus exact match antara embed dan extract

4. **Capacity**: Program akan menolak embed jika ukuran secret file melebihi kapasitas cover audio

## Troubleshooting

### Error "FFmpeg not found"
Install FFmpeg dan pastikan ada di PATH sistem

### Error "No module named 'pygame'"
```bash
pip install pygame
```

### Error "Capacity insufficient"
- Gunakan cover audio yang lebih panjang
- Kurangi ukuran secret file
- Gunakan n-LSB yang lebih tinggi (2-4)

### Error pada Extract
- Pastikan menggunakan file hasil embed (format WAV)
- Pastikan key sama persis dengan saat embed
- File stego tidak boleh dikonversi/dikompresi setelah embed