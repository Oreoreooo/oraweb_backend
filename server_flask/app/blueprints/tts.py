import edge_tts
import asyncio
import tempfile
import os
from flask import current_app

class TTSService:
    def __init__(self):
        self.voice = 'zh-CN-XiaoxiaoNeural'  # 默认中文声音
        
    async def text_to_speech(self, text: str, voice: str = None) -> str:
        """
        将文本转换为语音并返回音频文件路径
        """
        if not voice:
            voice = self.voice
            
        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        output_path = temp_file.name
        temp_file.close()
        
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
            return output_path
        except Exception as e:
            # 如果创建失败，删除临时文件
            if os.path.exists(output_path):
                os.unlink(output_path)
            raise e
    
    def text_to_speech_sync(self, text: str, voice: str = None) -> str:
        """
        同步版本的文本转语音
        """
        return asyncio.run(self.text_to_speech(text, voice))
    
    @staticmethod
    def get_available_voices():
        """
        获取可用的语音列表
        """
        return {
            # 中文语音
            'zh-CN-XiaoxiaoNeural': '中文女声(晓晓)',
            'zh-CN-YunxiNeural': '中文男声(云希)',
            'zh-CN-YunyangNeural': '中文男声(云扬)',
            'zh-CN-XiaoyiNeural': '中文女声(晓伊)',
            'zh-CN-YunjianNeural': '中文男声(云健)',
            'zh-CN-XiaoshuangNeural': '中文女声(晓双)',
            
            # 英文语音
            'en-US-JennyNeural': 'English Female (Jenny)',
            'en-US-GuyNeural': 'English Male (Guy)',
            'en-US-AriaNeural': 'English Female (Aria)',
            'en-US-DavisNeural': 'English Male (Davis)',
            
            # 其他语言
            'ja-JP-NanamiNeural': 'Japanese Female (Nanami)',
            'ko-KR-SunHiNeural': 'Korean Female (SunHi)',
            'fr-FR-DeniseNeural': 'French Female (Denise)',
            'de-DE-KatjaNeural': 'German Female (Katja)',
        }
