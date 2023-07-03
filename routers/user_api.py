from fastapi import APIRouter, Depends, Cookie, Response
from fastapi.responses import JSONResponse

from .auth import login_url, generate_token, get_token_from_user_id, get_user_from_token
from .typing_classes import User

router = APIRouter(prefix='/auth')


@router.get("/login_link")
async def login_link():
    return JSONResponse({
        'url': await login_url()
    })


@router.get("/callback")
async def callback(response: Response, token: str = Depends(generate_token)):
    response.set_cookie(key='access_token', value=token)
    return JSONResponse({
        'message': 'successful'
    })


@router.get("/user", response_model=User)
async def get_user(token: str = Depends(get_token_from_user_id)):
    user = await get_user_from_token(token)
    return user
