# -*- coding: utf-8 -*-
"""
音频发音服务模块：
1. 优先调用母语者纯正真人原声 MP3 发音（美音/英音可选），并本地缓存 (audio_cache)，实现 0 毫秒秒播
2. 本地断网或长句长文本自动回退到 Windows 系统本地 TTS 语音朗读
"""
import os
import re
import urllib.parse
import hashlib
import threading
import requests
from PyQt6.QtCore import QObject, QUrl, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtTextToSpeech import QTextToSpeech

class AudioService(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)

        # 本地 TTS 兜底引擎
        try:
            self.tts = QTextToSpeech(self)
        except Exception:
            self.tts = None

        self.cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def say(self, text: str, voice_type: int = 2):
        """
        播放英文发音：
        - voice_type: 2 为标准美音 (American)，1 为标准英音 (British)
        - 优先播放真人原声 MP3；若无网络或长难句，自动回退到本地系统 TTS
        """
        clean_text = text.strip()
        if not clean_text:
            return

        # 单词或短语优先真人纯正原声
        is_short = len(clean_text.split()) <= 6
        if is_short:
            md5_key = hashlib.md5(f"{clean_text.lower()}_{voice_type}".encode('utf-8')).hexdigest()
            local_file = os.path.join(self.cache_dir, f"{md5_key}.mp3")

            # 命中本地已缓存真人音频
            if os.path.exists(local_file) and os.path.getsize(local_file) > 1000:
                self._play_local_file(local_file)
                return

            # 异步下载真人原声并播放
            def fetch_and_play():
                try:
                    url = f"https://dict.youdao.com/dictvoice?audio={urllib.parse.quote(clean_text)}&type={voice_type}"
                    r = self.session.get(url, timeout=3.0)
                    if r.status_code == 200 and len(r.content) > 1000:
                        with open(local_file, "wb") as f:
                            f.write(r.content)
                        QTimer.singleShot(0, lambda: self._play_local_file(local_file))
                        return
                except Exception:
                    pass

                # 网络失败兜底：本地 TTS
                QTimer.singleShot(0, lambda: self._tts_fallback(clean_text))

            threading.Thread(target=fetch_and_play, daemon=True).start()
        else:
            # 长整句长文本：系统 TTS 或在线整句
            self._tts_fallback(clean_text)

    def _play_local_file(self, path: str):
        try:
            self.player.setSource(QUrl.fromLocalFile(os.path.abspath(path)))
            self.player.play()
        except Exception:
            pass

    def _tts_fallback(self, text: str):
        if self.tts:
            try:
                self.tts.say(text)
            except Exception:
                pass
