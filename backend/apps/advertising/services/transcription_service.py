"""
Transcrição síncrona de áudio para o chat do agente de Omni Ads — mesmo modelo
(Whisper) já usado para áudios do WhatsApp em apps/qualifier/transcriber.py,
mas síncrona (o usuário espera o texto aparecer antes de enviar a mensagem).
"""
from openai import OpenAI


def transcribe_audio_file(file, openai_api_key: str) -> str:
    """
    `file` chega como um UploadedFile do Django (InMemoryUploadedFile ou
    TemporaryUploadedFile), que não é bytes/IOBase/PathLike — o SDK da OpenAI
    recusa esse tipo direto (assert_is_file_content). Passar como tupla
    (nome, conteúdo, content_type) é a forma documentada pelo SDK para upload
    a partir de conteúdo que não é um arquivo real em disco.
    """
    client = OpenAI(api_key=openai_api_key)
    result = client.audio.transcriptions.create(
        model='whisper-1',
        file=(file.name or 'audio.webm', file.read(), file.content_type or 'audio/webm'),
        language='pt',
    )
    return result.text.strip()
