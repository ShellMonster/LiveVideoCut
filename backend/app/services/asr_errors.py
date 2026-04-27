class TranscriptionError(Exception):
    """Base error for ASR transcription failures."""
    def __init__(self, message: str, provider: str = "unknown"):
        self.provider = provider
        super().__init__(message)

class AuthError(TranscriptionError):
    """API key / credential issue."""

class ASRTimeoutError(TranscriptionError):
    """Request or polling timed out."""

class APIError(TranscriptionError):
    """External API returned an error (rate limit, server error, etc)."""

class NoSpeechError(TranscriptionError):
    """Legitimate case: audio has no detectable speech. Returns empty result, not an error per se."""
