import os

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


security = HTTPBearer()

COACH_API_KEY = os.environ["COACH_API_KEY"]


def verify_coach_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    if credentials.credentials != COACH_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )

    return True
