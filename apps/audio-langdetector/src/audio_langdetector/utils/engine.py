import logging
import os
import torch
from speechbrain.inference.classifiers import EncoderClassifier

logger = logging.getLogger(__name__)

WHISPER_SUPPORTED_LANGUAGES = {
    "af", "am", "ar", "as", "az", "ba", "be", "bg", "bn", "bo", "br", "bs", "ca", "cs",
    "cy", "da", "de", "el", "en", "es", "et", "eu", "fa", "fi", "fo", "fr", "gl", "gu",
    "ha", "haw", "he", "hi", "hr", "ht", "hu", "hy", "id", "is", "it", "ja", "jw", "ka",
    "kk", "km", "kn", "ko", "la", "lb", "ln", "lo", "lt", "lv", "mg", "mi", "mk", "ml",
    "mn", "mr", "ms", "mt", "my", "ne", "nl", "nn", "no", "oc", "pa", "pl", "ps", "pt",
    "ro", "ru", "sa", "sd", "si", "sk", "sl", "sn", "so", "sq", "sr", "su", "sv", "sw",
    "ta", "te", "tg", "th", "tk", "tl", "tr", "tt", "uk", "ur", "uz", "vi", "yi", "yo",
    "zh", "yue"
}

LEGACY_MAPPING = {
    "iw": "he",
    "jv": "jw",
    "mold": "ro",
}

class VoxLinguaEngine:
    _instance = None

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading LanguageID Model on {self.device}...")
        run_opts = {"device": self.device} if self.device == "cuda" else None

        self.classifier = EncoderClassifier.from_hparams(
            source="speechbrain/lang-id-voxlingua107-ecapa",
            savedir=f"{os.getenv('HF_HOME', '')}/cache/speechbrain/lang-id-voxlingua107-ecapa",
            run_opts=run_opts
        )
        logger.info("LanguageID Model loaded successfully.")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def detect(self, audio_path: str):
        signal = self.classifier.load_audio(audio_path)
        prediction = self.classifier.classify_batch(signal)

        accuracy = prediction[1].exp().item()
        label_raw = prediction[3][0]
        lang_code = label_raw.split(":")[0].strip()

        if lang_code in LEGACY_MAPPING:
            logger.info(f"Mapping legacy code '{lang_code}' to '{LEGACY_MAPPING[lang_code]}'")
            lang_code = LEGACY_MAPPING[lang_code]

        if lang_code not in WHISPER_SUPPORTED_LANGUAGES:
            logger.warning(
                f"Detected language '{lang_code}' is not supported by Whisper. Ignoring (will use auto-detect).")
            return None, accuracy

        return lang_code, accuracy