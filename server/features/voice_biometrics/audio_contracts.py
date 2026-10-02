from pydantic import BaseModel

class AudioStreamFrame(BaseModel):
    device_id: str
    sample_rate: int = 16000
    pcm_base64: str
    timestamp: float

class BiometricVerificationResult(BaseModel):
    is_verified: bool
    speaker_id: str
    confidence_score: float
    detected_wake_word: bool

class TTSRequest(BaseModel):
    text: str
    voice_profile: str = "it_IT-alan-medium"
    speed: float = 1.0
