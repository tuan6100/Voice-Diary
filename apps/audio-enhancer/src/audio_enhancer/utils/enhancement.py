import os

import torch
import torchaudio
import logging
import asyncio
from pathlib import Path
from speechbrain.inference.separation import SepformerSeparation

logger = logging.getLogger(__name__)

# 🔒 Semaphore để bảo vệ GPU
_GPU_SEMAPHORE = asyncio.Semaphore(1)


class AudioEnhancerModel:
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            logger.info("Loading SpeechBrain Sepformer model...")
            run_opts = {"device": "cuda"} if torch.cuda.is_available() else {"device": "cpu"}
            cls._model = SepformerSeparation.from_hparams(
                source="speechbrain/sepformer-wham16k-enhancement",
                savedir=f"{os.getenv('HF_HOME', '')}/cache/speechbrain/sepformer-wham16k-enhancement",
                run_opts=run_opts
            )
            logger.info(f"Model loaded on {run_opts['device']}")
        return cls._model


async def denoise_audio(input_path: str, output_path: str):
    async with _GPU_SEMAPHORE:
        model = AudioEnhancerModel.get_model()
        input_path = str(Path(input_path).resolve()).replace("\\", "/")
        output_path = str(Path(output_path).resolve()).replace("\\", "/")
        logger.debug(f"Denoising {input_path}")
        with torch.no_grad():
            est_sources = model.separate_file(path=input_path)
            enhanced_audio = est_sources[:, :, 0].detach().cpu()
            torchaudio.save(output_path, enhanced_audio, 16000)
