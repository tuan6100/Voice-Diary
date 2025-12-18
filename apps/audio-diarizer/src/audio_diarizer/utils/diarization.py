import torch
import logging

from omegaconf import ListConfig
from pyannote.audio import Pipeline

from audio_diarizer.core.config import settings

logger = logging.getLogger(__name__)


class DiarizationPipeline:
    _instance = None

    @classmethod
    def get_pipeline(cls):
        if cls._instance is None:
            torch.serialization.add_safe_globals([ListConfig])
            _original_torch_load = torch.load
            def _trusted_load(*args, **kwargs):
                kwargs['weights_only'] = False
                return _original_torch_load(*args, **kwargs)
            torch.load = _trusted_load

            cls._instance = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=settings.HF_TOKEN,
            )
            if torch.cuda.is_available():
                cls._instance.to(torch.device("cuda"))
                logger.info("Diarization pipeline moved to GPU.")
            else:
                logger.warning("Running Diarization on CPU. This will be slow!")
            logger.info("Loading Pyannote Diarization Pipeline...")
        return cls._instance


def diarize_audio(file_path: str):
    pipeline = DiarizationPipeline.get_pipeline()
    diarization = pipeline(file_path)
    result = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        result.append({
            "start": turn.start,
            "end": turn.end,
            "speaker": speaker
        })

    return result