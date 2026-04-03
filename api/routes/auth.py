from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from api.auth import verify_password, create_access_token, ADMIN_USERNAME, ADMIN_PASSWORD_HASH, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user
from datetime import timedelta

router = APIRouter(prefix = "/auth", tags = ["auth"])

@router.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username == ADMIN_USERNAME and verify_password(form_data.password, ADMIN_PASSWORD_HASH):
        token = create_access_token(
            data = {"sub": form_data.username, "role": "admin"},
            expires_delta = timedelta(minutes = ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
    )

@router.get("/me")
def get_me(current_user: dict, dict = Depends(get_current_user)):
    return current_user