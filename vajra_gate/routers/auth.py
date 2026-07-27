from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mcp_cli.services.users import authenticate_user, register_user, user_count
from vajra_gate.auth import create_access_token

router = APIRouter()


class AuthRequest(BaseModel):
    username: str
    password: str


@router.post("/api/auth/register")
async def register(body: AuthRequest):
    err = register_user(body.username, body.password)
    if err:
        raise HTTPException(status_code=409, detail=err)
    token = create_access_token(body.username)
    return {"token": token, "username": body.username}


@router.post("/api/auth/login")
async def login(body: AuthRequest):
    if not authenticate_user(body.username, body.password):
        if user_count() == 0:
            err = register_user(body.username, body.password)
            if err:
                raise HTTPException(status_code=400, detail=err)
            token = create_access_token(body.username)
            return {"token": token, "username": body.username, "first_login": True}
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(body.username)
    return {"token": token, "username": body.username}
