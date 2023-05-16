from multiprocessing import connection
import os
from re import U
from unittest import result
from fastapi import HTTPException, Depends

from config.api_config import settings
from repository import user_repository as crud_users
from sqlalchemy.orm import Session
from db.connection import get_db
from utils.utils import object_as_dict
from entity.user_entity import UserInit, UserCreate, User
from service.user import user_util
from src.shared.security import deps

def get_admin_info(db: Session):
    user = crud_users.get_user_by_username(db, "admin")
    return object_as_dict(user)


async def create_init_user(passwd: UserInit, db: Session = Depends(get_db)):
    init_user = settings.INIT_USER
    user_util.validate_password(init_user.get("username"), passwd.password)
    db_user = crud_users.get_user_by_username(db, username=init_user.get("username"))
    if db_user:
        raise HTTPException(status_code=409, detail="Username already registered")
    else:
        try:
            return crud_users.create_init_user(db=db, password=passwd.password)
        except Exception as err:
            raise HTTPException(status_code=400, detail=str(err))

async def create_user(
        user: UserCreate, 
        current_user: User = Depends(deps.get_current_active_user),
        db: Session = Depends(get_db)
):
    # TODO: user 권한 validation
    db_user = crud_users.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    user_util.validate_password(user.username, user.password)
    try:
        result = crud_users.create_user(db=db, user=user)
        # TODO: logging 추가
        return result
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err))
