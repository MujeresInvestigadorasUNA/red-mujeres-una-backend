from fastapi import APIRouter, Depends, Query, File, UploadFile, Form
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.auth import require_token
from app.controllers.users_controller import UserController
from app.schemas.users import UserCreate, UserUpdate, UserOut, UsersDetailsOut, UserLogin, UserLoginResponse, UserUpdateResponse
from typing import Optional

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_model=list[UsersDetailsOut])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    return UserController.list_users(db, skip=skip, limit=limit)

@router.get("/researchers", response_model=list[UsersDetailsOut])
def get_researchers(
    is_public: bool = Query(False, description="If true, return only researchers with is_public=True. If false, return all researchers."),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Get all researchers (user_type_id = 2).
    
    Query Parameters:
    - is_public (bool): Filter to only public researchers. Default: False (returns all researchers)
    - skip (int): Number of records to skip (for pagination)
    - limit (int): Maximum number of records to return (1-200, default: 50)
    
    Examples:
    - GET /users/researchers → All researchers
    - GET /users/researchers?is_public=true → Only public researchers
    - GET /users/researchers?is_public=true&skip=10&limit=20 → Public researchers with pagination
    """
    return UserController.get_researchers(db, is_public, skip, limit)

@router.get("/{user_id}", response_model=UsersDetailsOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    return UserController.get_user(db, user_id)

@router.post("/register", status_code=201)
async def register_user_with_photo(
    email: str = Form(...),
    password: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    user_type_id: int = Form(...),
    photo: Optional[UploadFile] = File(None),
    user_profession: Optional[str] = Form(None),
    user_description: Optional[str] = Form(None),
    is_public: bool = Form(False),
    db: Session = Depends(get_db),
):
    """
    Registra un usuario CON foto de perfil.
    
    Envía los datos como multipart/form-data:
    - email (texto)
    - password (texto)
    - first_name (texto)
    - last_name (texto)
    - user_type_id (número)
    - photo (archivo - opcional)
    - user_profession (texto - opcional)
    - user_description (texto - opcional)
    - is_public (booleano - opcional, default: false)
    """
    return await UserController.register_with_photo(
        db=db,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        user_type_id=user_type_id,
        photo=photo,
        user_profession=user_profession,
        user_description=user_description,
        is_public=is_public
    )

@router.post("/", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    return UserController.create_user(db, payload)

@router.post("/{user_id}/profile-picture")
async def update_profile_picture(
    user_id: int,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Actualiza la foto de perfil de un usuario existente.
    """
    return await UserController.update_profile_picture(db, user_id, photo)

@router.put("/{user_id}", response_model=UserUpdateResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    _: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    return UserController.update_user(db, user_id, payload)

@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    return UserController.delete_user(db, user_id)

@router.post("/login", response_model=UserLoginResponse)
def login(user: UserLogin, db: Session = Depends(get_db)):
    return UserController.login(db, user)