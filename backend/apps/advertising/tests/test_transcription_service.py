from unittest.mock import patch, MagicMock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from apps.advertising.services.transcription_service import transcribe_audio_file


class TranscribeAudioFileTests(SimpleTestCase):
    """
    audio_file chega do request.FILES como um Django UploadedFile — o SDK da
    OpenAI recusa esse tipo direto (não é bytes/IOBase/PathLike), então
    transcribe_audio_file precisa converter para a tupla (nome, conteúdo,
    content_type) documentada pelo SDK.
    """

    @patch('apps.advertising.services.transcription_service.OpenAI')
    def test_passes_uploaded_file_as_tuple_never_the_django_object_directly(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.audio.transcriptions.create.return_value = MagicMock(text=' Quanto gastamos essa semana? ')

        uploaded = SimpleUploadedFile('gravacao.webm', b'fake-audio-bytes', content_type='audio/webm')
        text = transcribe_audio_file(uploaded, openai_api_key='sk-test')

        self.assertEqual(text, 'Quanto gastamos essa semana?')
        _, kwargs = mock_client.audio.transcriptions.create.call_args
        file_arg = kwargs['file']
        self.assertIsInstance(file_arg, tuple)
        self.assertEqual(file_arg, ('gravacao.webm', b'fake-audio-bytes', 'audio/webm'))

    @patch('apps.advertising.services.transcription_service.OpenAI')
    def test_falls_back_to_default_name_and_content_type_when_missing(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.audio.transcriptions.create.return_value = MagicMock(text='ok')

        uploaded = MagicMock(name=None, content_type=None)
        uploaded.name = None
        uploaded.content_type = None
        uploaded.read.return_value = b'bytes'
        transcribe_audio_file(uploaded, openai_api_key='sk-test')

        _, kwargs = mock_client.audio.transcriptions.create.call_args
        name, content, content_type = kwargs['file']
        self.assertEqual(name, 'audio.webm')
        self.assertEqual(content_type, 'audio/webm')
