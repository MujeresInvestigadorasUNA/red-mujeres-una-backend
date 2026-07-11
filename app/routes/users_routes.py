from fastapi import APIRouter, Depends, Query, File, UploadFile, Form, Body
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.auth import require_token, require_admin
from app.controllers.users_controller import UserController
from app.schemas.users import UserCreate, UserUpdate, UserTypeUpdate, UserOut, UsersDetailsOut, UserUpdateResponse, ProfilePictureUrlOut
from typing import Optional

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/cleanup-firebase")
def cleanup_firebase_user(
    email: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    return UserController.cleanup_firebase_user(db, email)


@router.post("/password-reset")
def send_password_reset(
    email: str = Body(..., embed=True),
):
    return UserController.send_password_reset(email)


@router.post("/email-verification")
def send_email_verification(
    email: str = Body(..., embed=True),
):
    return UserController.send_email_verification(email)


@router.get("/exists")
def user_exists(
    email: str = Query(..., min_length=3),
    db: Session = Depends(get_db),
):
    return UserController.exists(db, email)

@router.get("", response_model=list[UsersDetailsOut])
def list_users(
    skip: int = Query(0, ge=0),
    limit: Optional[int] = Query(None, ge=1),
    _: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    return UserController.list_users(db, skip=skip, limit=limit)

#Check this method, it is not being used and it is the same as get_user, maybe we can delete it
@router.get("/researchers", response_model=list[UsersDetailsOut])
def get_researchers(
    is_public: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    return UserController.get_researchers(db, is_public, skip, limit)


@router.get("/by-email", response_model=UsersDetailsOut)
def get_user_by_email(
    email: str = Query(...),
    _: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    return UserController.get_user_by_email(db, email)


@router.get("/{user_id}", response_model=UsersDetailsOut)
def get_user(
    user_id: int,
    _: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    return UserController.get_user(db, user_id)


@router.post("/register", status_code=201)
async def register_user_with_photo(
    email: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    user_type_id: int = Form(...),
    photo: Optional[UploadFile] = File(None),
    user_profession: Optional[str] = Form(None),
    user_description: Optional[str] = Form(None),
    is_public: bool = Form(False),
    db: Session = Depends(get_db),
):
    return await UserController.register_with_photo(
        db=db,
        email=email,
        first_name=first_name,
        last_name=last_name,
        user_type_id=user_type_id,
        photo=photo,
        user_profession=user_profession,
        user_description=user_description,
        is_public=is_public,
    )


@router.post("", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    return UserController.create_user(db, payload)


@router.get("/{user_id}/profile-picture-url", response_model=ProfilePictureUrlOut)
def get_profile_picture_url(
    user_id: int,
    expires_minutes: int = Query(60, ge=1, le=120),
    _: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    return UserController.get_profile_picture_url(db, user_id, expires_minutes)


@router.post("/{user_id}/profile-picture")
async def update_profile_picture(
    user_id: int,
    photo: UploadFile = File(...),
    _: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    return await UserController.update_profile_picture(db, user_id, photo)


@router.put("/{user_id}", response_model=UserUpdateResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    _: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    return UserController.update_user(db, user_id, payload)


@router.put("/{user_id}/user-type", response_model=UserUpdateResponse)
def update_user_type(
    user_id: int,
    payload: UserTypeUpdate,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return UserController.update_user_type(db, user_id, payload.user_type_id)


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    _: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    return UserController.delete_user(db, user_id)


