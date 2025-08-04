import pyaudio
import wave
import numpy as np
import threading
import queue
import time
from io import BytesIO
import os
import warnings

# 配置环境变量以减少警告
os.environ["MODELSCOPE_DISABLE_WARNINGS"] = "1"
os.environ["FUNASR_DISABLE_UPDATE"] = "1"
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from ..config import Config

class ASRService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ASRService, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self):
        try:
            # 使用本地模型路径
            import os
            model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models", "SenseVoiceSmall")
            
            print(f"Loading ASR model from: {model_path}")
            
            # 首先尝试不使用remote_code
            try:
                # Initialize the ASR model without remote code
                self.model = AutoModel(
                    model=model_path,
                    vad_model="fsmn-vad",
                    vad_kwargs={"max_single_segment_time": 30000},
                    device="cuda:0" if Config.USE_CUDA else "cpu",
                    disable_update=True,
                    trust_remote_code=False  # 不信任远程代码
                )
                print("✅ Model loaded without remote code")
            except Exception as e1:
                print(f"⚠️ Failed to load without remote code: {e1}")
                try:
                    # 如果失败，尝试使用本地model.py
                    self.model = AutoModel(
                        model=model_path,
                        trust_remote_code=True,
                        vad_model="fsmn-vad",
                        vad_kwargs={"max_single_segment_time": 30000},
                        device="cuda:0" if Config.USE_CUDA else "cpu",
                        disable_update=True
                    )
                    print("✅ Model loaded with local model.py")
                except Exception as e2:
                    print(f"⚠️ Failed with local model.py: {e2}")
                    # 最后尝试使用在线模型
                    self.model = AutoModel(
                        model="iic/SenseVoiceSmall",
                        trust_remote_code=True,
                        vad_model="fsmn-vad",
                        vad_kwargs={"max_single_segment_time": 30000},
                        device="cuda:0" if Config.USE_CUDA else "cpu",
                        disable_update=True
                    )
                    print("✅ Model loaded from online repository")
            
            # Audio parameters
            self.CHUNK = 1024
            self.FORMAT = pyaudio.paFloat32
            self.CHANNELS = 1
            self.RATE = 16000
            
            # Initialize PyAudio
            self.p = pyaudio.PyAudio()
            
            # Queue for audio chunks
            self.audio_queue = queue.Queue()
            self.is_recording = False
            self.is_running = True
            
            # Test microphone access
            self._test_microphone()
            
        except Exception as e:
            raise Exception(f"Failed to initialize ASR service: {str(e)}")

    def _test_microphone(self):
        """Test if microphone is accessible"""
        try:
            stream = self.p.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            stream.close()
        except Exception as e:
            raise Exception(f"Microphone not accessible: {str(e)}")

    def start_recording(self):
        """Start recording audio from microphone"""
        if self.is_recording:
            return {"error": "Already recording"}
        
        try:
            self.is_recording = True
            self.audio_queue = queue.Queue()
            
            def record_audio():
                try:
                    stream = self.p.open(
                        format=self.FORMAT,
                        channels=self.CHANNELS,
                        rate=self.RATE,
                        input=True,
                        frames_per_buffer=self.CHUNK
                    )
                    
                    while self.is_recording:
                        try:
                            data = stream.read(self.CHUNK, exception_on_overflow=False)
                            audio_data = np.frombuffer(data, dtype=np.float32)
                            self.audio_queue.put(audio_data)
                        except Exception as e:
                            print(f"Error reading audio: {str(e)}")
                            continue
                    
                    stream.stop_stream()
                    stream.close()
                except Exception as e:
                    print(f"Error in recording thread: {str(e)}")
                    self.is_recording = False
            
            # Start recording in a separate thread
            self.record_thread = threading.Thread(target=record_audio)
            self.record_thread.daemon = True  # Make thread daemon so it exits when main program exits
            self.record_thread.start()
            
            return {"message": "Recording started"}
        except Exception as e:
            self.is_recording = False
            return {"error": f"Failed to start recording: {str(e)}"}

    def stop_recording(self):
        """Stop recording and process the audio"""
        if not self.is_recording:
            return {"error": "Not recording"}
        
        try:
            self.is_recording = False
            if hasattr(self, 'record_thread'):
                self.record_thread.join(timeout=2.0)  # Wait up to 2 seconds for thread to finish
            
            # Process the recorded audio
            buffer = []
            while not self.audio_queue.empty():
                try:
                    audio_chunk = self.audio_queue.get_nowait()
                    buffer.extend(audio_chunk)
                except queue.Empty:
                    break
            
            if not buffer:
                return {"error": "No audio recorded"}
            
            # Convert buffer to numpy array
            audio_data = np.array(buffer)
            
            # Create in-memory WAV file
            wav_buffer = BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(self.CHANNELS)
                wf.setsampwidth(self.p.get_sample_size(self.FORMAT))
                wf.setframerate(self.RATE)
                wf.writeframes(audio_data.tobytes())
            
            # Reset buffer position to start
            wav_buffer.seek(0)
            
            try:
                # Perform ASR
                res = self.model.generate(
                    input=wav_buffer,
                    cache={},
                    language="auto",
                    use_itn=True,
                    batch_size_s=60,
                    merge_vad=True,
                    merge_length_s=15,
                )
                
                # Process result
                text = rich_transcription_postprocess(res[0]["text"])
                return {"text": text.strip()}
            except Exception as e:
                return {"error": f"ASR Error: {str(e)}"}
            finally:
                wav_buffer.close()
        except Exception as e:
            return {"error": f"Failed to stop recording: {str(e)}"}

    def cleanup(self):
        """Clean up resources"""
        try:
            self.is_running = False
            self.is_recording = False
            if hasattr(self, 'record_thread'):
                self.record_thread.join(timeout=2.0)
            self.p.terminate()
        except Exception as e:
            print(f"Error during cleanup: {str(e)}") 