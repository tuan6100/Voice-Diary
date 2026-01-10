import logging
import torch
from speechbrain.inference.classifiers import EncoderClassifier

logger = logging.getLogger(__name__)


class  VoxLinguaEngine:
    _instance = None

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading LanguageID Model on {self.device}...")
        run_opts = {"device": self.device} if self.device == "cuda" else None

        self.classifier = EncoderClassifier.from_hparams(
            source="speechbrain/lang-id-voxlingua107-ecapa",
            savedir="tmp_models/lang_id_model",
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
        accuracy = prediction[0].item()
        label_raw = prediction[3][0]
        lang_code = label_raw.split(":")[0].strip()
        return lang_code, accuracy