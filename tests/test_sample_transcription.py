from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

from bender_media import transcription as stt
from bender_voice.hardware import Hardware, HardwareError


class SampleTranscriptionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.config={'data_dir':self.temp.name,'sample_transcription':{'model':'small'}};self.hardware=Hardware(self.config)
        self.directory=stt.model_directory(self.config)
        self.audio=Path(self.temp.name)/'clip.wav'
        with wave.open(str(self.audio),'wb') as audio:
            audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(16000);audio.writeframes(b'\0\0'*64000)
        reset=patch.multiple(stt,_model=None,_model_key=None);reset.start();self.addCleanup(reset.stop)

    def ready(self):
        self.directory.mkdir(parents=True,exist_ok=True)
        for name in ('model.bin','config.json','tokenizer.json','vocabulary.json'):(self.directory/name).write_bytes(b'test')

    def engine(self):
        word=SimpleNamespace(word=' Bonjour',start=0.2,end=0.9,probability=0.96)
        engine=Mock();engine.transcribe.side_effect=lambda *a,**kw:(iter([SimpleNamespace(text=' Bonjour.',start=0,end=1,words=[word])]),None)
        constructor=Mock(return_value=engine)
        return SimpleNamespace(WhisperModel=constructor),engine

    def test_cpu_french_offline_settings_timestamps_and_cached_model(self):
        self.ready();module,engine=self.engine();events=[]
        with patch.dict('sys.modules',faster_whisper=module):
            text,words=stt.transcribe(self.hardware,self.audio,lambda *event:events.append(event))
            stt.transcribe(self.hardware,self.audio)
        self.assertEqual(text,'Bonjour.');self.assertEqual(words,[dict(word='Bonjour',start=0.2,end=0.9,conf=0.96)])
        module.WhisperModel.assert_called_once_with(str(self.directory),device='cpu',compute_type='int8',cpu_threads=2,num_workers=1,local_files_only=True)
        options=engine.transcribe.call_args.kwargs
        self.assertEqual(options['language'],'fr');self.assertEqual(options['task'],'transcribe')
        self.assertEqual(options['beam_size'],5);self.assertTrue(options['word_timestamps']);self.assertTrue(options['vad_filter'])
        self.assertFalse(options['condition_on_previous_text'])
        self.assertTrue(all(len(event)==1 for event in events))  # Timestamp coverage is not a percent of computation.
        self.assertTrue(any('1.0 s / 4.0 s' in event[0] for event in events))

    def test_missing_tokenizer_never_triggers_an_implicit_download(self):
        self.directory.mkdir(parents=True)
        for name in ('model.bin','config.json','vocabulary.json'):(self.directory/name).write_bytes(b'test')
        module,engine=self.engine()
        with patch.dict('sys.modules',faster_whisper=module):
            with self.assertRaisesRegex(HardwareError,'Modèle Whisper absent'):stt.transcribe(self.hardware,self.audio)
        module.WhisperModel.assert_not_called()

    def test_lazy_decode_error_releases_the_model_lock(self):
        self.ready();module,engine=self.engine()
        def failed():
            yield SimpleNamespace(text='début',start=0,end=1,words=[])
            raise RuntimeError('decode failure')
        engine.transcribe.return_value=(failed(),None);engine.transcribe.side_effect=None
        with patch.dict('sys.modules',faster_whisper=module):
            with self.assertRaisesRegex(HardwareError,'Transcription Whisper impossible'):stt.transcribe(self.hardware,self.audio)
            self.assertFalse(stt._lock.locked())
            engine.transcribe.return_value=(iter([]),None)
            self.assertEqual(stt.transcribe(self.hardware,self.audio),('',[]))

    def test_download_is_explicit_and_repeated_setup_reuses_the_model(self):
        # Exercise a non-canonical data root, as Windows TEMP may use an 8.3
        # name or a junction while inside() returns the resolved directory.
        alias=Path(self.temp.name)/'temporary-alias'
        alias.mkdir()
        self.config['data_dir']=str(alias/'..')
        download=Mock(side_effect=lambda *a,**kw:self.ready())
        with patch.dict('sys.modules',{'faster_whisper.utils':SimpleNamespace(download_model=download)}):
            stt.download(self.config);stt.download(self.config)
        self.assertEqual(download.call_count,1);self.assertEqual(download.call_args.args,('small',))
        cache=Path(download.call_args.kwargs['cache_dir']).resolve()
        self.assertTrue(cache.is_relative_to(Path(self.config['data_dir']).resolve()))
        self.assertEqual(Path(download.call_args.kwargs['output_dir']).resolve(),self.directory.resolve())

    def test_vosk_requires_explicit_configuration(self):
        self.config['sample_transcription']={'engine':'vosk'}
        with patch('bender_media.processing.transcribe',return_value=('texte',[])) as vosk:
            self.assertEqual(stt.transcribe(self.hardware,self.audio),('texte',[]));vosk.assert_called_once()

    def test_default_quality_and_model_memory_released_between_batches(self):
        self.assertEqual(stt.profile({'data_dir':self.temp.name})['model'],'medium')
        self.ready();module,engine=self.engine()
        with patch.dict('sys.modules',faster_whisper=module):
            stt.transcribe(self.hardware,self.audio);self.assertIsNotNone(stt._model)
            stt.release();self.assertIsNone(stt._model)
            stt.transcribe(self.hardware,self.audio)
        self.assertEqual(module.WhisperModel.call_count,2)
