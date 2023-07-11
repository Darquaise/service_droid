from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from .auth import login_url, generate_token, user_is_authenticated

router = APIRouter(prefix='/api')


@router.get("/login_link")
async def login_link():
    return JSONResponse({
        'url': await login_url()
    })


@router.get("/callback")
async def callback(token: str = Depends(generate_token)):
    response = JSONResponse({
        'successful': True
    })
    response.set_cookie(
        key='access_token',
        value=token
    )
    return response


@router.get("/authenticated")
async def is_authenticated(is_auth: bool = Depends(user_is_authenticated)):
    return JSONResponse({
        'successful': is_auth
    })
