"""
Transcrição assíncrona de áudios WhatsApp via OpenAI Whisper.

Uso:
    transcribe_audio_async(message_id, file_path, openai_api_key)

Roda em thread daemon para não bloquear o webhook.
Falha silenciosamente — a mensagem permanece sem transcrição se ocorrer erro.
"""

import logging
import threading

from django.core.files.storage import default_storage
from openai import OpenAI

logger = logging.getLogger(__name__)


def transcribe_audio_async(message_id: int, file_path: str, openai_api_key: str) -> None:
    """Lança thread daemon para transcrever o áudio e salvar em Message.transcription."""

    def _run() -> None:
        try:
            client = OpenAI(api_key=openai_api_key)
            with default_storage.open(file_path, 'rb') as audio_file:
                result = client.audio.transcriptions.create(
                    model='whisper-1',
                    file=audio_file,
                    language='pt',
                )
            transcription_text = result.text.strip()
            if transcription_text:
                from apps.conversations.models import Message
                Message.objects.filter(pk=message_id).update(transcription=transcription_text)
                logger.info('transcriber: message %s transcribed (%d chars)', message_id, len(transcription_text))
        except Exception as exc:
            logger.warning('transcribe_audio_async error (message=%s): %s', message_id, exc)

    threading.Thread(target=_run, daemon=True).start()
