from pydantic.v1 import BaseModel

class MobileLoginRequest(BaseModel):
    code: str