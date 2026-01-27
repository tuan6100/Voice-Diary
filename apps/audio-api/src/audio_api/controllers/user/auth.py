from datetime import datetime, timedelta

from authlib.jose import jwt
from fastapi import HTTPException, APIRouter
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from google.auth.transport import requests as google_requests

from audio_api.cores.config import settings
from audio_api.cores.redis import get_redis_client
from audio_api.dtos.request.auth import MobileLoginRequest
from audio_api.models.user import User

router = APIRouter()

@router.post("/mobile-login")
async def mobile_login(payload: MobileLoginRequest):
    try:
        # 1. Cấu hình Flow để đổi code lấy token
        flow = Flow.from_client_config(
            client_config={
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=settings.GOOGLE_SCOPES.split(" ")
        )
        flow.redirect_uri = 'postmessage'
        # 2. Đổi Code lấy Token (Access Token + Refresh Token)
        flow.fetch_token(code=payload.code)
        credentials = flow.credentials
        # 3. Lấy thông tin User từ ID Token (có sẵn trong credentials)
        id_info = id_token.verify_oauth2_token(
            credentials.id_token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )
        email = id_info.get('email')
        if not email:
            raise HTTPException(400, "Invalid Google Token: Email missing")
        # Lưu User
        user = await User.find_one(User.email == email)
        if not user:
            user = User(
                username=id_info.get('name'),
                email=email,
                avatar_url=id_info.get('picture')
            )
            await user.insert()
        else:
            user.avatar_url = id_info.get('picture')
            user.display_name = id_info.get('name')
            await user.save()
        # 5. Lưu Google Access Token vào Redis (Cho chức năng export Google Docs)
        redis = get_redis_client()
        await redis.setex(
            f"google_token:{user.id}",
            3500,
            credentials.token
        )
        await redis.close()
        # 6. Tạo JWT App Token
        app_token = _create_jwt_token(str(user.id))
        # 7. Trả về JSON (Mobile sẽ parse cái này)
        return {
            "access_token": app_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.display_name,
                "avatar": user.avatar_url
            }
        }

    except ValueError as e:
        raise HTTPException(400, f"Token verification failed: {str(e)}")
    except Exception as e:
        raise HTTPException(400, f"Mobile login failed: {str(e)}")


def _create_jwt_token(user_id: str):
    payload = {
        "sub": user_id,
        "exp": datetime.now(datetime.UTC) + timedelta(days=7)
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")