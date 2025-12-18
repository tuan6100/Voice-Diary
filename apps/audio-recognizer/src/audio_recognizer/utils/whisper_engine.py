import whisperx
import torch
import logging
import gc
from omegaconf.listconfig import ListConfig

logger = logging.getLogger(__name__)

class WhisperEngine:
    _instance = None

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        self.batch_size = 16

        torch.serialization.add_safe_globals([ListConfig])
        _original_torch_load = torch.load
        def _trusted_load(*args, **kwargs):
            kwargs['weights_only'] = False
            return _original_torch_load(*args, **kwargs)
        torch.load = _trusted_load

        self.model = whisperx.load_model(
            "large-v3",
            self.device,
            compute_type=self.compute_type
        )
        self.align_model, self.align_metadata = whisperx.load_align_model(
            language_code="vi",
            device=self.device
        )
        logger.info("WhisperX Models loaded successfully.")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def transcribe_file(self, audio_path: str):
        try:
            logger.info(f"Transcribing: {audio_path}")
            audio = whisperx.load_audio(audio_path)
            result = self.model.transcribe(audio, batch_size=self.batch_size)
            logger.info("Aligning result...")
            result_aligned = whisperx.align(
                result["segments"],
                self.align_model,
                self.align_metadata,
                audio,
                self.device,
                return_char_alignments=False
            )
            gc.collect()
            if self.device == "cuda":
                torch.cuda.empty_cache()

            return result_aligned["word_segments"]
        except Exception as e:
            logger.error(f"Whisper Engine Error: {e}")
            raise e