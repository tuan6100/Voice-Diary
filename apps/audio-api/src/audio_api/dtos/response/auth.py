from typing import Optional

from audio_api.cores.model import CamelModel

class UserResponse(CamelModel):
    id: str
    email: str
    name: str
    avatar: Optional[str] = None

class LoggedInResponse(CamelModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

