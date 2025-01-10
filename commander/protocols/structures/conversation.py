from base64 import b64encode


class Conversation:
    ROLE_SYSTEM = "system"
    ROLE_USER = "user"

    def __init__(self, model: str, temperature: float):
        self.model = model
        self.temperature = temperature
        self.system_prompt: list[str] = []
        self.user_prompt: list[str] = []
        self.audios: list[dict] = []

    def add_audio(self, audio: bytes, audio_format: str) -> None:
        if audio:
            self.audios.append({
                "format": audio_format,
                "data": b64encode(audio).decode("utf-8"),
            })

    def to_dict(self) -> dict:
        content = [{
            "type": "text",
            "text": "\n".join(self.user_prompt),
        }]
        for audio in self.audios:
            content.append({
                "type": "input_audio",
                "input_audio": audio,
            })

        return {
            "model": self.model,
            "modalities": ["text"],
            "messages": [
                {"role": self.ROLE_SYSTEM, "content": "\n".join(self.system_prompt)},
                {"role": self.ROLE_USER, "content": content},
            ],
            "temperature": self.temperature,
        }
