"""
Transcrição síncrona de áudio para o chat do agente de Omni Ads — mesmo modelo
(Whisper) já usado para áudios do WhatsApp em apps/qualifier/transcriber.py,
mas síncrona (o usuário espera o texto aparecer antes de enviar a mensagem).
"""
from openai import OpenAI


def transcribe_audio_file(file, openai_api_key: str) -> str:
    client = OpenAI(api_key=openai_api_key)
    result = client.audio.transcriptions.create(
        model='whisper-1',
        file=file,
        language='pt',
    )
    return result.text.strip()
