import os
import json
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from typing import Optional
import bcrypt
import jwt
import aiofiles
import aiosqlite
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 토큰 설정 및 기밀값
SECRET_KEY = "super-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

db_dir = os.path.dirname(__file__)
os.makedirs(db_dir, exist_ok=True)
DB_PATH = os.path.join(db_dir, "user_profile.db")

# 정적 파일 및 업로드 디렉토리 정의
STATIC_DIR = os.path.join(db_dir, "static")
UPLOAD_DIR = os.path.join(db_dir, "profile_images")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# --- [비밀번호 암호화 및 검증 헬퍼 (수업 버전)] ---
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# --- [SQLite 연결 + 테이블 생성] ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                profile_image_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.commit()
    yield


app = FastAPI(lifespan=lifespan)

# CORS + 정적 파일 마운트 연동 설정
origins = ['*']
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/profile_images", StaticFiles(directory=UPLOAD_DIR), name="profile_images")


async def get_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# --- [Pydantic 입출력 데이터 모델 스키마] ---
class UserCreate(BaseModel):
    username: str
    email: str  
    password: str


class UserLogin(BaseModel):
    email: str  
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


# --- [라우터 API 엔드포인트 정의] ---
@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html", status_code=303)


# [회원가입]
@app.post("/register")
async def register(payload: UserCreate, db=Depends(get_db)):
    async with db.execute("SELECT id FROM users WHERE email = ?", (payload.email,)) as cursor:
        if await cursor.fetchone():
            raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pass = hash_password(payload.password)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    empty_json = json.dumps({})

    await db.execute(
        """INSERT INTO users (username, email, hashed_password, profile_image_json, created_at, updated_at) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        (payload.username, payload.email, hashed_pass, empty_json, now_str, now_str),
    )
    await db.commit()
    return {"message": "User registered successfully"}


# [로그인]
@app.post("/login", response_model=Token)
async def login(payload: UserLogin, db=Depends(get_db)):
    async with db.execute("SELECT * FROM users WHERE email = ?", (payload.email,)) as cursor:
        user = await cursor.fetchone()

    if not user or not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(
        data={"sub": user["email"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}


# [JWT 인증 토큰 검증 의존성 함수]
async def get_current_user_email(token: str = Depends(oauth2_scheme), db=Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except jwt.PyJWTError:  
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    async with db.execute("SELECT email FROM users WHERE email = ?", (email,)) as cursor:
        user = await cursor.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user["email"]


# [내 정보 조회]
@app.get("/me")
async def get_me(current_user_email: str = Depends(get_current_user_email), db=Depends(get_db)):
    async with db.execute(
        "SELECT id, username, email, profile_image_json, created_at FROM users WHERE email = ?", 
        (current_user_email,)
    ) as cursor:
        user = await cursor.fetchone()
        
    user_dict = dict(user)
    user_dict["profile_image_json"] = json.loads(user_dict["profile_image_json"]) if user_dict["profile_image_json"] else {}
    return user_dict


# [사용자 목록 조회]
@app.get("/api/users")
async def get_all_users(db=Depends(get_db)):
    async with db.execute("SELECT id, username, email, profile_image_json, created_at FROM users ORDER BY id DESC") as cursor:
        rows = await cursor.fetchall()
        
    result = []
    for row in rows:
        d = dict(row)
        d["profile_image_json"] = json.loads(d["profile_image_json"]) if d["profile_image_json"] else {}
        result.append(d)
    return result


# [사용자 상세 조회]
@app.get("/api/users/{user_id}")
async def get_user_detail(user_id: int, db=Depends(get_db)):
    async with db.execute("SELECT id, username, email, profile_image_json, created_at FROM users WHERE id = ?", (user_id,)) as cursor:
        user = await cursor.fetchone()
        
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user_dict = dict(user)
    user_dict["profile_image_json"] = json.loads(user_dict["profile_image_json"]) if user_dict["profile_image_json"] else {}
    return user_dict


# [기능: 사용자 정보 수정 + 프로필 이미지 업로드]
@app.post("/api/users/{user_id}/update")
async def update_user_profile(
    user_id: int,
    username: str = Form(...),
    image: Optional[UploadFile] = File(None),
    current_user_email: str = Depends(get_current_user_email),  # JWT 회원 검증 결합 완료
    db=Depends(get_db)
):
    async with db.execute("SELECT profile_image_json FROM users WHERE id = ?", (user_id,)) as cursor:
        row = await cursor.fetchone()
        
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
        
    current_meta = json.loads(row["profile_image_json"]) if row["profile_image_json"] else {}

    # 지시서 요구사항: aiofiles를 사용하여 이미지 파일 비동기 보관 처리
    if image and image.filename:
        filename = f"profile_{int(datetime.now().timestamp())}_{image.filename}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        async with aiofiles.open(file_path, "wb") as f:
            file_content = await image.read()
            await f.write(file_content)
            
        # 지시서 요구사항: 업로드 이미지 메타데이터 구조체 생성
        current_meta = {
            "origin_name": image.filename,
            "saved_name": filename,
            "file_path": f"/profile_images/{filename}",
            "size": len(file_content),
            "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 지시서 요구사항: json.dumps()를 써서 TEXT 컬럼에 넣기 위해 문자열 변환
    meta_json_str = json.dumps(current_meta)

    await db.execute(
        "UPDATE users SET username = ?, profile_image_json = ?, updated_at = ? WHERE id = ?",
        (username, meta_json_str, now_str, user_id)
    )
    await db.commit()
    
    # 지시서 요구사항: 업로드 이미지 메타데이터 응답 완수
    return {"status": "success", "meta_data": current_meta}


# [삭제 관리]
@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, db=Depends(get_db)):
    await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    await db.commit()
    return {"status": "success", "message": "User deleted successfully"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)