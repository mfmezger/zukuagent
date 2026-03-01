"""Service for local audio transcription using Parakeet."""

import sys
from pathlib import Path

from loguru import logger

from zukuagent.settings import settings

try:
    import onnx_asr
except ImportError:
    logger.error("onnx_asr not found. Please install dependencies: uv add 'onnx-asr[cpu,hub]'")
    onnx_asr = None


class ParakeetTranscriptionService:
    """An ultra-lean service class for local audio transcription using NVIDIA's Parakeet models.

    This version relies on ONNX Runtime instead of PyTorch, making it significantly
    smaller, faster on CPUs, and easier to install.
    """

    def __init__(self, model_name: str | None = None) -> None:
        """Initialize the transcription service and loads the model into memory.

        Recommended Models:
        - nemo-parakeet-tdt-0.6b-v3 : Multilingual, great balance of speed/accuracy.
        - nemo-parakeet-tdt-0.6b-v2 : English only.
        """
        if onnx_asr is None:
            msg = "Cannot initialize service: onnx_asr is not installed."
            raise RuntimeError(msg)

        self.model_name = model_name or settings.transcription_model
        logger.info(f"Loading ONNX Parakeet ASR model '{self.model_name}'.")
        logger.info("This will download the model on the first run. Please wait...")

        # Load the pre-trained Parakeet model via huggingface hub & onnx
        self.model = onnx_asr.load_model(self.model_name)

        logger.info("ONNX Model loaded successfully and is ready for transcription.")

    def transcribe(self, audio_file_path: str) -> str:
        """Transcribe a local audio file and return the text.

        Args:
            audio_file_path (str): The local path to the audio file.
                                   Ideally 16kHz Mono WAV.

        Returns:
            str: The transcribed text.

        """
        path = Path(audio_file_path)
        if not path.exists():
            msg = f"Audio file not found at path: {audio_file_path}"
            raise FileNotFoundError(msg)

        logger.info(f"Transcribing audio file: {audio_file_path}")

        # Recognize the audio file directly
        # onnx-asr recognize returns a simple string for short files
        result = self.model.recognize(audio_file_path)

        if result:
            logger.info("Transcription completed successfully.")
            return result

        logger.warning("Transcription completed, but no text was returned.")
        return ""


if __name__ == "__main__":
    # Simple CLI interface to test the service standalone
    import argparse

    parser = argparse.ArgumentParser(description="Test the ONNX Parakeet Transcription Service locally.")
    parser.add_argument("audio_file", help="Path to the audio file to transcribe.")
    parser.add_argument("--model", default=None, help="Parakeet ONNX model to use.")

    args = parser.parse_args()

    try:
        service = ParakeetTranscriptionService(model_name=args.model)
        result_text = service.transcribe(args.audio_file)
        logger.info("\n" + "=" * 50)
        logger.info("TRANSCRIPTION RESULT:")
        logger.info("=" * 50)
        logger.info(result_text)
        logger.info("=" * 50 + "\n")
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        sys.exit(1)
