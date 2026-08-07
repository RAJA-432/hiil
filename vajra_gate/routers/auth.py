import asyncio

from fastapi import APIRouter, HTTPException

from mcp_cli.services.users import authenticate_user, register_user, user_count
from vajra_gate.auth import create_access_token
from vajra_gate.models import AuthRequest, AuthResponse

router = APIRouter()


@router.post("/api/auth/register", response_model=AuthResponse)
async def register(body: AuthRequest):
    err = await asyncio.to_thread(register_user, body.username, body.password)
    if err:
        raise HTTPException(status_code=409, detail=err)
    token = create_access_token(body.username)
    return AuthResponse(token=token, username=body.username)


@router.post("/api/auth/login", response_model=AuthResponse)
async def login(body: AuthRequest):
    if not await asyncio.to_thread(authenticate_user, body.username, body.password):
        if user_count() == 0:
            err = await asyncio.to_thread(register_user, body.username, body.password)
            if err:
                raise HTTPException(status_code=400, detail=err)
            token = create_access_token(body.username)
            return AuthResponse(token=token, username=body.username, first_login=True)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(body.username)
    return AuthResponse(token=token, username=body.username)
