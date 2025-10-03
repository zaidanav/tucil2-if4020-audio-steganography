#!/usr/bin/env python3
"""
Demonstrasi fitur handling kapasitas yang telah ditingkatkan.
"""

import os
import sys
import tempfile
import wave
import struct
from pathlib import Path

# Add src to path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from stego.pipeline import (
    compute_capacity_for_file,
    calculate_payload_size, 
    check_embed_feasibility,
    embed_to_file,
    extract_to_file
)
from stego.capability_exceptions import CapacityError


def create_test_wav(path: str, duration: float = 1.0, sample_rate: int = 22050):
    """Buat file WAV test untuk demonstrasi."""
    import math
    samples = int(duration * sample_rate)
    frames = bytearray()
    
    for i in range(samples):
        # Sine wave dengan frekuensi 440 Hz
        value = int(16383 * math.sin(2 * math.pi * 440 * i / sample_rate))
        frames += struct.pack('<h', value)
    
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))


def demo_capacity_calculation():
    """Demonstrasi perhitungan kapasitas yang akurat."""
    print("=== DEMONSTRASI PERHITUNGAN KAPASITAS ===\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = os.path.join(tmpdir, "cover.wav")
        create_test_wav(wav_path, duration=2.0, sample_rate=22050)
        
        print(f"File cover: {wav_path}")
        print(f"Durasi: 2.0 detik, Sample rate: 22050 Hz")
        print(f"Total samples: {2.0 * 22050:,.0f}\n")
        
        for n_lsb in [1, 2, 3, 4]:
            capacity = compute_capacity_for_file(wav_path, n_lsb)
            capacity_bytes = capacity // 8
            
            print(f"n_lsb = {n_lsb}:")
            print(f"  Kapasitas: {capacity:,} bits ({capacity_bytes:,} bytes)")
            print(f"  Rumus: {2.0 * 22050:,.0f} samples × {n_lsb} LSB = {capacity:,} bits\n")


def demo_rejection():
    """Demonstrasi penolakan file yang melebihi kapasitas."""
    print("=== DEMONSTRASI PENOLAKAN FILE BERLEBIHAN ===\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Buat file cover kecil
        wav_path = os.path.join(tmpdir, "small_cover.wav")
        create_test_wav(wav_path, duration=0.1, sample_rate=8000)  # 800 samples
        
        # Buat file secret yang terlalu besar
        large_secret = os.path.join(tmpdir, "large_secret.txt")
        Path(large_secret).write_text("X" * 2000)  # File 2KB
        
        print(f"Cover audio: 0.1 detik × 8000 Hz = 800 samples")
        print(f"File secret: 2000 bytes = 16000 bits")
        
        n_lsb = 1
        capacity = compute_capacity_for_file(wav_path, n_lsb)
        print(f"Kapasitas dengan n_lsb={n_lsb}: {capacity} bits\n")
        
        try:
            out_path = os.path.join(tmpdir, "impossible.wav")
            embed_to_file(wav_path, large_secret, out_path, key="test", 
                         n_lsb=n_lsb, encrypt=False, use_rand_start=False)
        except CapacityError as e:
            print("✅ File berhasil ditolak dengan pesan error yang informatif:")
            print(f"{e}\n")


def demo_edge_cases():
    """Demonstrasi handling edge cases mendekati batas."""
    print("=== DEMONSTRASI EDGE CASES MENDEKATI BATAS ===\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = os.path.join(tmpdir, "edge_cover.wav")
        create_test_wav(wav_path, duration=0.5, sample_rate=8000)  # 4000 samples
        
        n_lsb = 2
        capacity = compute_capacity_for_file(wav_path, n_lsb)
        print(f"Kapasitas cover: {capacity} bits ({capacity // 8} bytes)")
        
        # Test berbagai ukuran file secret
        test_sizes = [
            ("Aman (50%)", capacity // 16),      # ~50% utilisasi 
            ("Mendekati (85%)", capacity // 10), # ~85% utilisasi
            ("Sangat dekat (95%)", capacity // 9) # ~95% utilisasi
        ]
        
        for desc, estimated_payload_bytes in test_sizes:
            secret_path = os.path.join(tmpdir, f"secret_{desc.replace(' ', '_')}.bin")
            Path(secret_path).write_bytes(b"T" * estimated_payload_bytes)
            
            # Cek feasibility
            result = check_embed_feasibility(wav_path, secret_path, "testkey", n_lsb)
            
            print(f"\n{desc} utilisasi:")
            print(f"  Ukuran secret: {estimated_payload_bytes} bytes")
            print(f"  Diperlukan: {result['need_bits']:,} bits")
            print(f"  Utilisasi: {result['utilization_percent']:.1f}%")
            print(f"  Status: {'✅ Bisa' if result['fits'] else '❌ Tidak bisa'}")
            print(f"  Rekomendasi: {result['recommendation']}")
            
            if result['fits']:
                # Coba embed dan extract
                out_path = os.path.join(tmpdir, f"stego_{desc.replace(' ', '_')}.wav")
                try:
                    psnr = embed_to_file(wav_path, secret_path, out_path, key="testkey",
                                       n_lsb=n_lsb, encrypt=False, use_rand_start=True)
                    
                    # Test extraction
                    extract_dir = os.path.join(tmpdir, "extracted")
                    os.makedirs(extract_dir, exist_ok=True)
                    extracted_path, flags = extract_to_file(out_path, "testkey", extract_dir)
                    
                    # Verifikasi
                    original = Path(secret_path).read_bytes()
                    extracted = Path(extracted_path).read_bytes()
                    
                    if original == extracted:
                        print(f"  ✅ Embed & extract berhasil (PSNR: {psnr:.2f} dB)" if psnr else "  ✅ Embed & extract berhasil")
                    else:
                        print(f"  ❌ Data tidak sama setelah extract")
                        
                except Exception as e:
                    print(f"  ❌ Error: {e}")


def demo_partial_lsb():
    """Demonstrasi handling partial LSB groups."""
    print("=== DEMONSTRASI PARTIAL LSB GROUPS ===\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = os.path.join(tmpdir, "partial_cover.wav")
        create_test_wav(wav_path, duration=0.2, sample_rate=8000)
        
        # Test dengan berbagai ukuran yang tidak habis dibagi n_lsb
        test_cases = [
            ("5 bytes = 40 bits", 5, 3),  # 40 bits dengan 3-LSB = 13 groups + 1 bit sisa
            ("7 bytes = 56 bits", 7, 3),  # 56 bits dengan 3-LSB = 18 groups + 2 bits sisa
            ("3 bytes = 24 bits", 3, 4),  # 24 bits dengan 4-LSB = 6 groups tepat
        ]
        
        for desc, size_bytes, n_lsb in test_cases:
            secret_path = os.path.join(tmpdir, f"partial_{size_bytes}b.bin")
            test_data = bytes(range(size_bytes))  # Data unik untuk verifikasi
            Path(secret_path).write_bytes(test_data)
            
            print(f"{desc} dengan {n_lsb}-LSB:")
            
            total_bits = size_bytes * 8
            full_groups = total_bits // n_lsb
            remaining_bits = total_bits % n_lsb
            
            print(f"  Total bits: {total_bits}")
            print(f"  Full {n_lsb}-bit groups: {full_groups}")
            print(f"  Remaining bits: {remaining_bits}")
            
            try:
                out_path = os.path.join(tmpdir, f"stego_partial_{size_bytes}b.wav")
                embed_to_file(wav_path, secret_path, out_path, key="partial_test",
                             n_lsb=n_lsb, encrypt=False, use_rand_start=False)
                
                # Extract dan verifikasi
                extract_dir = os.path.join(tmpdir, "extracted_partial")
                os.makedirs(extract_dir, exist_ok=True)
                extracted_path, flags = extract_to_file(out_path, "partial_test", extract_dir)
                
                extracted_data = Path(extracted_path).read_bytes()
                if test_data == extracted_data:
                    print(f"  ✅ Partial LSB handling berhasil")
                else:
                    print(f"  ❌ Data corruption: {len(test_data)} → {len(extracted_data)}")
                    
            except Exception as e:
                print(f"  ❌ Error: {e}")
            
            print()


if __name__ == "__main__":
    print("DEMONSTRASI FITUR CAPACITY HANDLING")
    print("=" * 50)
    print()
    
    demo_capacity_calculation()
    print()
    
    demo_rejection()
    print()
    
    demo_edge_cases()
    print()
    
    demo_partial_lsb()
    print()
    
    print("=" * 50)
    print("Semua demonstrasi selesai!")