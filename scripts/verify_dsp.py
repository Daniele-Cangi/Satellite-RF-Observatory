
import numpy as np
from scipy import signal as scipy_signal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DSP-Verify")

def test_cfar():
    print("="*40)
    print("Verifying CA-CFAR Algorithm")
    print("="*40)
    
    # 1. Generate Synthetic Data
    sample_rate = 2.4e6
    num_samples = 16384
    
    # Noise (Gaussian)
    noise = (np.random.randn(num_samples) + 1j * np.random.randn(num_samples)) * 0.1
    
    # Signal (Sine wave at offset freq)
    t = np.arange(num_samples) / sample_rate
    target_freq = 100e3 # 100 kHz offset
    signal_power = 2.0 # Stronger than noise (0.1)
    sig = signal_power * np.exp(1j * 2 * np.pi * target_freq * t)
    
    data = noise + sig
    
    # 2. FFT (DSP Step 1)
    freqs, psd = scipy_signal.periodogram(
        data, 
        fs=sample_rate, 
        window='hann', 
        scaling='density',
        return_onesided=False
    )
    freqs = np.fft.fftshift(freqs)
    psd = np.fft.fftshift(psd)
    psd_db = 10 * np.log10(psd + 1e-12)
    
    print(f"[Data] PSD Mean: {np.mean(psd_db):.2f} dB")
    print(f"[Data] PSD Max: {np.max(psd_db):.2f} dB")
    
    # 3. Apply CA-CFAR (The Logic from Scheduler)
    guard_cells = 4
    ref_cells = 16
    bias = 10.0 # 10dB # Adjusted bias for test to ensure detection
    
    kernel = np.ones(1 + (guard_cells*2) + (ref_cells*2))
    kernel[ref_cells : ref_cells + 1 + (guard_cells*2)] = 0
    kernel = kernel / (ref_cells * 2)
    
    psd_linear = 10**(psd_db/10)
    noise_estimate = scipy_signal.convolve(psd_linear, kernel, mode='same')
    
    # Adaptive Threshold
    # Using the same logic as Scheduler: 
    # adaptive_threshold_linear = noise_estimate * (10**(10/10))
    # Let's use the explicit 'bias' variable here for clarity in test
    adaptive_threshold_linear = noise_estimate * (10**(bias/10))
    
    detected_indices = np.where(psd_linear > adaptive_threshold_linear)[0]
    
    print(f"[CFAR] Detections Found: {len(detected_indices)}")
    
    # 4. Analyze Detections
    detected_freqs = freqs[detected_indices]
    
    # Cluster
    peaks = []
    if len(detected_indices) > 0:
        clusters = np.split(detected_indices, np.where(np.diff(detected_indices) > 2)[0] + 1)
        for cluster in clusters:
             if len(cluster) == 0: continue
             peak_idx = cluster[np.argmax(psd_db[cluster])]
             peaks.append(freqs[peak_idx])

    print(f"[CFAR] Peaks Identified: {len(peaks)}")
    for p in peaks:
        print(f"    > Freq: {p/1e3:.2f} kHz")
        
    # Validation
    found = False
    for p in peaks:
        if abs(p - target_freq) < 1000: # Within 1kHz
            found = True
            print(f"[SUCCESS] Target at {target_freq/1e3} kHz detected at {p/1e3:.2f} kHz")
            
    if not found:
        print("[FAIL] Target not detected.")
        exit(1)
    else:
        print("[PASS] DSP Verification Complete.")

if __name__ == "__main__":
    test_cfar()
