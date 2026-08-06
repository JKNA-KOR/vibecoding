# AGENTS.md

# AI Coding Agent Rules
Version: 1.0

이 프로젝트는 증권 거래 시스템(Trading System)이다.
AI Agent는 아래 규칙을 반드시 준수한다.

---

# 1. 기본 원칙

## 1.1 정확성이 속도보다 중요하다.

잘 동작하는 코드를 우선한다.

성능 최적화는 요구사항이 있을 때만 수행한다.

추측하지 않는다.

모르는 API는 생성하지 않는다.

필요하면 TODO를 남긴다.

---

## 1.2 기존 코드를 최대한 존중한다.

동일한 패턴을 유지한다.

기존 아키텍처를 변경하지 않는다.

리팩토링은 별도 PR에서 수행한다.

---

## 1.3 금융 시스템 특성

모든 거래 데이터는 신뢰 가능해야 한다.

계좌번호

주문번호

체결번호

잔고

금액

수량

손익

위 데이터는 절대 임의 생성하지 않는다.

---

# 2. 코드 작성 규칙

## 함수

하나의 함수는 하나의 역할만 수행한다.

함수 길이는 50줄 이하를 권장한다.

3단계 이상의 중첩 if는 금지한다.

Magic Number 사용 금지.

공통 코드는 반드시 함수로 분리한다.

---

## 클래스

SRP(Single Responsibility Principle)를 따른다.

의존성은 생성자를 통해 주입한다.

전역 상태(Global State)를 최소화한다.

---

## 변수명

의미 있는 이름 사용

Good

order_quantity

account_balance

average_price

Bad

a

temp

data1

---

## 예외 처리

모든 외부 API 호출은 예외 처리한다.

DB 작업은 Rollback을 고려한다.

예외를 무시하지 않는다.

except:
    pass

사용 금지

---

## Logging

print() 사용 금지

logging 사용

로그 레벨

DEBUG

INFO

WARNING

ERROR

CRITICAL

민감 정보는 로그에 출력 금지

비밀번호

Access Token

Secret Key

계좌번호 전체

주민번호

---

# 3. 보안 규칙

## 절대 금지

SQL Injection 가능한 코드

Shell Injection

eval()

exec()

pickle.loads()

yaml.load()

subprocess(shell=True)

MD5

SHA1

하드코딩된 비밀번호

Access Token 하드코딩

API Secret 저장

개인정보 평문 저장

HTTPS 우회

SSL 검증 비활성화

---

## 인증

JWT 검증 필수

토큰 만료 검사

권한 검사

최소 권한 원칙(Least Privilege)

관리자 권한 남용 금지

---

## DB

ORM 사용 우선

Raw SQL은 Parameter Binding 필수

Transaction 사용

Rollback 처리

---

## 환경 변수

민감 정보는 반드시

.env

또는

Secret Manager

사용

---

# 4. API 규칙

RESTful API 사용

HTTP Status 준수

200 OK

201 Created

204 No Content

400 Bad Request

401 Unauthorized

403 Forbidden

404 Not Found

409 Conflict

500 Internal Server Error

---

## API 응답

성공

{
    "success": true,
    "data": {}
}

실패

{
    "success": false,
    "message": "...",
    "code": "..."
}

---

# 5. 데이터베이스 규칙

DDL 변경은 Migration 사용

PK 변경 금지

삭제 대신 Soft Delete 우선 고려

Timestamp는 UTC 저장

모든 테이블은

created_at

updated_at

을 가진다.

---

# 6. 증권 시스템 규칙

주문은 반드시 Transaction 처리

체결 데이터는 수정 금지

잔고 계산은 실시간 계산보다 검증된 로직 사용

금액 계산은 Decimal 사용

float 사용 금지

시간은 UTC 저장

거래소 시간은 View Layer에서 변환

---

# 7. PR 규칙

PR 제목 Prefix

feat:

fix:

refactor:

docs:

test:

style:

perf:

build:

ci:

chore:

예시

feat: 계좌 조회 API 추가

fix: 주문 체결 오류 수정

---

PR에는 반드시 포함

변경 내용

테스트 결과

영향 범위

스크린샷(API면 Swagger)

Breaking Change 여부

---

금지

테스트 없는 PR

컴파일 실패 PR

Lint 실패 PR

TODO만 있는 PR

사용하지 않는 코드 포함

---

# 8. 테스트 규칙

테스트는 필수

pytest 사용

테스트 위치

tests/

예시

tests/
    api/
    service/
    repository/

파일명

test_account.py

test_order.py

test_login.py

---

실행

pytest

전체

pytest tests/

커버리지

pytest --cov=app

최소 Coverage

80%

신규 기능은 반드시 테스트 작성

버그 수정은 Regression Test 추가

---

# 9. 코드 스타일

PEP8 준수

Black Formatter 사용

isort 사용

Flake8 통과

mypy 오류 금지

---

# 10. 문서화

모든 Public 함수는 Docstring 작성

Swagger(OpenAPI) 최신 상태 유지

README 변경사항 반영

환경 변수 변경 시 .env.example 수정

---

# 11. AI Agent 행동 규칙

AI는 추측으로 API를 생성하지 않는다.

존재하지 않는 함수 호출 금지.

TODO는 명확하게 작성한다.

코드를 삭제하기 전에 영향 범위를 설명한다.

Breaking Change는 반드시 명시한다.

보안 규칙은 절대 우회하지 않는다.

테스트 없이 완료라고 하지 않는다.

컴파일 여부를 확인하지 못하면 확인하지 못했다고 명시한다.

---

# 12. 작업 완료 체크리스트

- 코드가 빌드된다.
- 테스트가 통과한다.
- Lint를 통과한다.
- 보안 규칙을 위반하지 않는다.
- 민감 정보가 포함되지 않았다.
- 로그에 개인정보가 없다.
- Decimal을 사용하였다.
- Transaction을 사용하였다.
- Swagger를 업데이트하였다.
- README를 업데이트하였다.
- Migration을 작성하였다(필요 시).
- Breaking Change를 확인하였다.

---

# 13. 절대 금지 사항

❌ print() 디버깅 코드 Commit

❌ 테스트 없는 기능 추가

❌ float로 금액 계산

❌ Secret Commit

❌ Master/Main 직접 Push

❌ Force Push

❌ SQL 문자열 연결

❌ eval(), exec()

❌ except: pass

❌ shell=True

❌ 인증 우회

❌ SSL 검증 비활성화

❌ 권한 검사 생략

❌ Hard Coding

❌ Dead Code 방치

---

# 14. 권장 기술 스택

Backend
- Python 3.12+
- Flask
- SQLAlchemy
- Alembic

Database
- PostgreSQL

Authentication
- JWT

Testing
- pytest
- pytest-cov

Formatting
- black
- isort
- flake8
- mypy

Documentation
- Swagger(OpenAPI)
- Markdown

---

이 문서는 모든 AI Agent와 개발자가 반드시 준수해야 한다.
규칙을 위반하는 코드는 생성하거나 승인하지 않는다.