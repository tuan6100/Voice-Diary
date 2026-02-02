from audio_api.cores.model import CamelModel


class GoogleLoginRequest(CamelModel):
    code: str

class TraditionalLoginRequest(CamelModel):
    email: str
    password: str

class TraditionalRegisterRequest(CamelModel):
    name: str
    email: str
    password: str