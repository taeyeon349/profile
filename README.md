👤 프로필 관리 시스템 (Profile Management System)

이 프로젝트는 사용자 로그인/회원가입, 프로필 정보 관리, 프로필 이미지 업로드(Multipart) 기능을 제공하는 웹 애플리케이션입니다.



🛠 기술 스택

Frontend: HTML5, CSS3, jQuery, JavaScript (Fetch/Ajax)



Backend: FastAPI (Python)



Database: SQLite (SQLAlchemy)



✨ 주요 기능

회원 인증: JWT 토큰을 활용한 로그인 및 회원가입



프로필 관리: 본인의 이름 수정 및 프로필 이미지 업로드



상세 조회: 전체 사용자 목록 조회 및 상세 정보 확인



회원 탈퇴: 계정 정보 및 프로필 데이터 삭제



📂 프로젝트 구조

Plaintext

project/

├── main.py             # FastAPI 백엔드 서버

├── models.py           # DB 모델 정의

├── database.py         # DB 연결 설정

├── static/             # 프론트엔드 파일 (index.html, css, js)

└── profile\_images/     # 업로드된 이미지 저장 경로

🚀 설치 및 실행 방법

1\. 백엔드 서버 실행

Bash

\# 의존성 패키지 설치

pip install fastapi uvicorn sqlalchemy python-multipart



\# 서버 시작

uvicorn main:app --host 0.0.0.0 --port 8001 --reload

2\. 프론트엔드 설정

index.html 파일을 엽니다.



<script> 내의 API\_BASE 상수를 현재 서버의 IP (백엔드)주소와 포트로 설정하세요.



JavaScript

const API\_BASE = "http://\[내\_IP\_주소(백엔드)]:8001";

🔐 보안

JWT(JSON Web Token)를 사용하여 인증된 사용자만 프로필 수정 및 삭제가 가능합니다.



이미지 업로드 시, 인증 토큰(Authorization: Bearer <token>)을 헤더에 포함해야 합니다.



🤝 협업 안내

이 프로젝트는 백엔드와 프론트엔드가 분리된 환경에서 개발되었습니다.



API 엔드포인트 수정 시, 프론트엔드의 API\_BASE 주소가 일치하는지 반드시 확인해주세요.

