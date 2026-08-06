# SENSOR.md

# AI Self Correction Sensor

Version: 1.0

이 문서는 AI가 자신의 산출물을 자동으로 검증하기 위한 규칙이다.

---

# 목적

Sensor는 오류를 발견하면 종료하지 않는다.

오류 내용을 분석한다.

원인을 찾는다.

수정한다.

다시 실행한다.

성공할 때까지 반복한다.

---

# 반복 규칙

Repeat

↓

Lint

↓

Type Check

↓

Security Scan

↓

Unit Test

↓

Coverage

↓

Build

↓

PASS ?

YES → 종료

NO → 수정 후 다시 실행

---

# Sensor가 감지해야 하는 오류

## Formatting

Black

isort

## Lint

flake8

## Type

mypy

## Security

bandit

safety

SQL Injection

Hard Coding

JWT 검증 누락

Secret 노출

SSL 비활성화

eval()

exec()

subprocess(shell=True)

pickle.loads()

yaml.load()

except: pass

print()

float 금액 계산

---

## Test

pytest

Regression Test

Coverage

---

## Build

Compile Error

Import Error

Circular Import

Migration Error

---

# Self Correction Rule

오류가 발생하면

1.
오류 메시지를 읽는다.

2.
원인을 분석한다.

3.
최소 수정으로 해결한다.

4.
다시 테스트한다.

5.
새로운 오류가 발생하면 반복한다.

6.
PASS가 될 때까지 종료하지 않는다.

---

# 수정 원칙

한 번에 하나의 문제만 수정한다.

불필요한 리팩토링 금지.

동작을 변경하지 않는다.

기존 테스트를 깨지 않는다.

---

# 종료 조건

다음 항목이 모두 PASS여야 한다.

PASS

✓ Build

✓ Lint

✓ Type Check

✓ Security

✓ Unit Test

✓ Coverage

✓ Migration

PASS가 아니면 작업 완료를 선언하지 않는다.