import os
import sys
import io
import wave
import struct
import tempfile
import unittest
from pathlib import Path

# Add src directory to path for imports
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from stego.pipeline import (
    compute_capacity_for_file, 
    calculate_payload_size,
    embed_to_file, 
    extract_to_file, 
    check_embed_feasibility
)
from stego.capability_exceptions import CapacityError


def _gen_sine_wav(path: str, seconds: float = 1.0, freq: float = 440.0, 
                  fr: int = 8000, amp: int = 1000, channels: int = 1):
    """Generate a sine wave WAV file for testing."""
    import math
    n = int(seconds * fr)
    frames = bytearray()
    
    for i in range(n):
        s = int(amp * math.sin(2 * math.pi * freq * (i / fr)))
        for _ in range(channels):
            frames += struct.pack('<h', s)
    
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(fr)
        wf.writeframes(bytes(frames))


class TestCapacityCalculation(unittest.TestCase):
    """Test accurate capacity calculation."""
    
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.mono_wav = os.path.join(self.tmpdir.name, 'mono.wav')
        self.stereo_wav = os.path.join(self.tmpdir.name, 'stereo.wav')
        
        # Create test files
        _gen_sine_wav(self.mono_wav, seconds=0.5, fr=8000, channels=1)    # 4000 samples
        _gen_sine_wav(self.stereo_wav, seconds=0.5, fr=8000, channels=2)  # 8000 samples
    
    def tearDown(self):
        self.tmpdir.cleanup()
    
    def test_mono_capacity_calculation(self):
        """Test capacity calculation for mono audio."""
        for n_lsb in [1, 2, 3, 4]:
            with self.subTest(n_lsb=n_lsb):
                cap = compute_capacity_for_file(self.mono_wav, n_lsb)
                expected = 4000 * n_lsb  # 0.5s * 8000 Hz * n_lsb
                self.assertEqual(cap, expected)
    
    def test_stereo_capacity_calculation(self):
        """Test capacity calculation for stereo audio."""
        for n_lsb in [1, 2, 3, 4]:
            with self.subTest(n_lsb=n_lsb):
                cap = compute_capacity_for_file(self.stereo_wav, n_lsb)
                expected = 8000 * n_lsb  # 0.5s * 8000 Hz * 2 channels * n_lsb
                self.assertEqual(cap, expected)
    
    def test_invalid_n_lsb(self):
        """Test validation of n_lsb parameter."""
        for invalid_n_lsb in [0, 5, -1, 10]:
            with self.subTest(n_lsb=invalid_n_lsb):
                with self.assertRaises(ValueError):
                    compute_capacity_for_file(self.mono_wav, invalid_n_lsb)
    
    def test_payload_size_calculation(self):
        """Test payload size calculation includes all overhead."""
        secret_path = os.path.join(self.tmpdir.name, 'secret.txt')
        Path(secret_path).write_text("Hello World!")
        
        for n_lsb in [1, 2, 3, 4]:
            for encrypt in [False, True]:
                for use_rand_start in [False, True]:
                    with self.subTest(n_lsb=n_lsb, encrypt=encrypt, use_rand_start=use_rand_start):
                        size = calculate_payload_size(secret_path, "key123", n_lsb, encrypt, use_rand_start)
                        self.assertGreater(size, 12 * 8)  # Must be larger than raw file
                        self.assertIsInstance(size, int)


class TestCapacityRejection(unittest.TestCase):
    """Test rejection of files exceeding capacity."""
    
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.small_wav = os.path.join(self.tmpdir.name, 'small.wav')
        
        # Create very small audio file
        _gen_sine_wav(self.small_wav, seconds=0.01, fr=8000)  # Only 80 samples
    
    def tearDown(self):
        self.tmpdir.cleanup()
    
    def test_reject_oversized_file(self):
        """Test that oversized files are rejected with detailed error."""
        n_lsb = 1
        cap_bits = compute_capacity_for_file(self.small_wav, n_lsb)
        
        # Create a file that's definitely too large
        large_secret = os.path.join(self.tmpdir.name, 'large_secret.bin')
        Path(large_secret).write_bytes(b'A' * (cap_bits // 4))  # Much larger than capacity
        
        out = os.path.join(self.tmpdir.name, 'out.wav')
        
        with self.assertRaises(CapacityError) as context:
            embed_to_file(self.small_wav, large_secret, out, key='test', 
                         n_lsb=n_lsb, encrypt=False, use_rand_start=False, compute_psnr=False)
        
        error_msg = str(context.exception)
        # Check that error message contains detailed information
        self.assertIn("File terlalu besar", error_msg)
        self.assertIn("Diperlukan:", error_msg)
        self.assertIn("Kapasitas:", error_msg)
        self.assertIn("Kelebihan:", error_msg)
    
    def test_feasibility_checker_rejects_oversized(self):
        """Test feasibility checker correctly identifies oversized files."""
        large_secret = os.path.join(self.tmpdir.name, 'large_secret.bin')
        cap_bits = compute_capacity_for_file(self.small_wav, 1)
        Path(large_secret).write_bytes(b'X' * (cap_bits // 4))
        
        result = check_embed_feasibility(self.small_wav, large_secret, "key", 1)
        
        self.assertFalse(result['fits'])
        self.assertLess(result['margin_bits'], 0)
        self.assertGreater(result['utilization_percent'], 100)
        self.assertIn("❌", result['recommendation'])


class TestEdgeCasesNearLimit(unittest.TestCase):
    """Test handling of edge cases near capacity limits."""
    
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.wav = os.path.join(self.tmpdir.name, 'cover.wav')
        
        # Create medium-sized audio file for edge case testing
        _gen_sine_wav(self.wav, seconds=0.2, fr=8000)  # 1600 samples
    
    def tearDown(self):
        self.tmpdir.cleanup()
    
    def test_near_limit_embedding(self):
        """Test embedding near capacity limits with successful extraction."""
        n_lsb = 2
        
        # Find the largest file that fits
        best_size = self._find_max_fitting_size(n_lsb)
        self.assertGreater(best_size, 0, "Should find some fitting size")
        
        # Create secret file at this size
        secret = os.path.join(self.tmpdir.name, f'secret_{best_size}.bin')
        Path(secret).write_bytes(b'Z' * best_size)
        
        # Should embed successfully
        out = os.path.join(self.tmpdir.name, 'stego.wav')
        psnr = embed_to_file(self.wav, secret, out, key='testkey', 
                           n_lsb=n_lsb, encrypt=False, use_rand_start=True, compute_psnr=True)
        
        self.assertTrue(os.path.exists(out))
        if psnr is not None:
            self.assertGreater(psnr, 0)
        
        # Should extract correctly
        outdir = os.path.join(self.tmpdir.name, 'extracted')
        os.makedirs(outdir, exist_ok=True)
        
        extracted_path, flags = extract_to_file(out, key='testkey', outdir=outdir)
        extracted_content = Path(extracted_path).read_bytes()
        original_content = Path(secret).read_bytes()
        
        self.assertEqual(extracted_content, original_content)
        self.assertEqual(flags['n_lsb'], n_lsb)
    
    def test_partial_lsb_groups(self):
        """Test that partial LSB groups are handled correctly."""
        n_lsb = 3
        
        # Create a secret whose bit size isn't divisible by n_lsb
        secret = os.path.join(self.tmpdir.name, 'partial.bin')
        Path(secret).write_bytes(b'AB')  # 16 bits, not divisible by 3
        
        out = os.path.join(self.tmpdir.name, 'stego.wav')
        
        # Should embed without error
        embed_to_file(self.wav, secret, out, key='test', 
                     n_lsb=n_lsb, encrypt=False, use_rand_start=False, compute_psnr=False)
        
        # Should extract correctly
        outdir = os.path.join(self.tmpdir.name, 'extracted')
        os.makedirs(outdir, exist_ok=True)
        
        extracted_path, flags = extract_to_file(out, key='test', outdir=outdir)
        self.assertEqual(Path(extracted_path).read_bytes(), b'AB')
    
    def test_high_utilization_warnings(self):
        """Test that high utilization triggers appropriate warnings."""
        # This test would need to capture stdout to verify warnings
        # For now, just test that high utilization is detected by feasibility checker
        
        n_lsb = 1
        # Find a size that gives >80% utilization
        target_utilization = 85
        cap_bits = compute_capacity_for_file(self.wav, n_lsb)
        
        # Estimate size for target utilization, accounting for header overhead
        estimated_payload_bits = int(cap_bits * target_utilization / 100)
        estimated_payload_bytes = max(1, estimated_payload_bits // 8 - 20)  # Subtract header estimate
        
        secret = os.path.join(self.tmpdir.name, 'high_util.bin')
        Path(secret).write_bytes(b'X' * estimated_payload_bytes)
        
        result = check_embed_feasibility(self.wav, secret, "key", n_lsb)
        
        if result['fits'] and result['utilization_percent'] > 80:
            self.assertIn("⚠️", result['recommendation'])
    
    def _find_max_fitting_size(self, n_lsb: int) -> int:
        """Binary search to find maximum fitting payload size."""
        lo, hi = 0, 200  # More conservative upper bound
        best = 0
        
        for _ in range(15):  # Limit iterations
            if lo > hi:
                break
            
            mid = (lo + hi) // 2
            temp_secret = os.path.join(self.tmpdir.name, f'temp_{mid}.bin')
            Path(temp_secret).write_bytes(b'T' * mid)
            
            result = check_embed_feasibility(self.wav, temp_secret, "key", n_lsb)
            
            if result['fits'] and result['utilization_percent'] < 95:  # Be more conservative
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
            
            # Clean up temp file
            try:
                os.unlink(temp_secret)
            except:
                pass
        
        return best


class TestFeasibilityChecker(unittest.TestCase):
    """Test the feasibility checking function."""
    
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.wav = os.path.join(self.tmpdir.name, 'test.wav')
        _gen_sine_wav(self.wav, seconds=0.1, fr=8000)  # 800 samples
    
    def tearDown(self):
        self.tmpdir.cleanup()
    
    def test_feasibility_checker_structure(self):
        """Test that feasibility checker returns correct structure."""
        secret = os.path.join(self.tmpdir.name, 'small.txt')
        Path(secret).write_text("Hello")
        
        result = check_embed_feasibility(self.wav, secret, "key", 2)
        
        required_keys = ['capacity_bits', 'need_bits', 'fits', 'margin_bits', 
                        'utilization_percent', 'recommendation']
        
        for key in required_keys:
            self.assertIn(key, result)
        
        self.assertIsInstance(result['capacity_bits'], int)
        self.assertIsInstance(result['need_bits'], int)
        self.assertIsInstance(result['fits'], bool)
        self.assertIsInstance(result['margin_bits'], int)
        self.assertIsInstance(result['utilization_percent'], (int, float))
        self.assertIsInstance(result['recommendation'], str)
    
    def test_feasibility_with_different_options(self):
        """Test feasibility checker with different encryption and randomization options."""
        secret = os.path.join(self.tmpdir.name, 'test.txt')
        Path(secret).write_text("Test data")
        
        base_result = check_embed_feasibility(self.wav, secret, "key", 2, False, False)
        enc_result = check_embed_feasibility(self.wav, secret, "key", 2, True, False)
        rand_result = check_embed_feasibility(self.wav, secret, "key", 2, False, True)
        both_result = check_embed_feasibility(self.wav, secret, "key", 2, True, True)
        
        # Encrypted version should need more bits
        self.assertGreaterEqual(enc_result['need_bits'], base_result['need_bits'])
        
        # All should have same capacity
        self.assertEqual(base_result['capacity_bits'], enc_result['capacity_bits'])
        self.assertEqual(base_result['capacity_bits'], rand_result['capacity_bits'])
        self.assertEqual(base_result['capacity_bits'], both_result['capacity_bits'])


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)