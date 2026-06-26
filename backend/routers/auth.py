from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import User, Organization, Configuration
from schemas import UserRegister, UserLogin, TokenResponse, UserResponse
from auth import get_password_hash, verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    # 1. Validate Organization logic
    if user_data.org_id and user_data.org_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Specify either org_id to join an organization or org_name to create one, not both."
        )
    if not user_data.org_id and not user_data.org_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify either org_id to join an organization or org_name to create one."
        )

    # Check if role is valid
    role = user_data.role.upper()
    if role not in ["ADMIN", "ANALYST"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be either ADMIN or ANALYST."
        )

    # 2. Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered."
        )

    org = None
    if user_data.org_id:
        org = db.query(Organization).filter(Organization.id == user_data.org_id).first()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found."
            )
    else:
        # Create organization
        org = Organization(name=user_data.org_name)
        db.add(org)
        db.flush()  # Flushes to DB to generate ID
        
        # Create default configuration for the organization
        default_config = Configuration(
            org_id=org.id,
            auto_execute_threshold=0.85,
            category_margin_floors={
                "electronics": 0.10,
                "apparel": 0.25,
                "home goods": 0.15
            }
        )
        db.add(default_config)

    # 3. Create User
    hashed_pwd = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_pwd,
        full_name=user_data.full_name,
        role=role,
        org_id=org.id
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Generate token
    token = create_access_token(data={"sub": user.id})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }


@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = create_access_token(data={"sub": user.id})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }
