import numpy as np
import torch
import torchaudio
from scipy import signal
from enum import Enum


class NoiseLevel(Enum):
    UNKNOWN = "UNKNOWN"
    VERY_CLEAN = "VERY_CLEAN"
    CLEAN = "CLEAN"
    LIGHT_NOISE = "LIGHT_NOISE"
    MODERATE_NOISE = "MODERATE_NOISE"
    HEAVY_NOISE = "HEAVY_NOISE"

    @classmethod
    def from_snr(cls, snr):
        if snr is None: return cls.UNKNOWN
        if snr > 20: return cls.VERY_CLEAN
        if snr > 15: return cls.CLEAN
        if snr > 10: return cls.LIGHT_NOISE
        if snr > 5: return cls.MODERATE_NOISE
        return cls.HEAVY_NOISE

def estimate_snr_spectral(audio_tensor: torch.Tensor, sr: int, frame_length=2048, hop_length=512) -> float:
    if torch.is_tensor(audio_tensor):
        audio = audio_tensor.numpy()
    else:
        audio = audio_tensor
    if audio.ndim > 1:
        audio = audio.flatten()
    f, t, Zxx = signal.stft(audio, sr, nperseg=frame_length, noverlap=frame_length - hop_length)
    power_spec = np.abs(Zxx) ** 2
    noise_floor = np.percentile(power_spec, 10, axis=1, keepdims=True)
    signal_estimate = np.median(power_spec, axis=1, keepdims=True)
    snr_per_freq = 10 * np.log10((signal_estimate / (noise_floor + 1e-10)))
    avg_snr = np.mean(snr_per_freq[snr_per_freq > -20])
    return float(avg_snr)

def check_audio_quality(file_path: str):
    audio, sr = torchaudio.load(file_path)
    snr = estimate_snr_spectral(audio, sr)
    level = NoiseLevel.from_snr(snr)
    need_denoise = level not in (NoiseLevel.VERY_CLEAN, NoiseLevel.CLEAN, NoiseLevel.LIGHT_NOISE)
    return {
        "snr": snr,
        "level": level.value,
        "need_denoise": need_denoise
    }