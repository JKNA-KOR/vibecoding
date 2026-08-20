from pathlib import Path
import shutil
import sys
import py_compile

TARGET = Path("app/market.py")
BACKUP = Path("app/market.py.before_gold_prediction_save")

if not TARGET.exists():
    print(f"ERROR: {TARGET} 파일이 없습니다.")
    sys.exit(1)

text = TARGET.read_text(encoding="utf-8")


# ============================================================
# 1. 이미 적용되어 있는지 확인
# ============================================================
has_save_method = "def save_gold_prediction(" in text
has_save_logic = "GOLD PREDICTION SAVED:" in text


if has_save_method and has_save_logic:
    print("OK: Gold prediction DB 저장 패치가 이미 적용되어 있습니다.")
    sys.exit(0)


# ============================================================
# 2. 백업
# ============================================================
if not BACKUP.exists():
    shutil.copy2(TARGET, BACKUP)
    print(f"OK: 백업 생성 -> {BACKUP}")
else:
    print(f"INFO: 기존 백업 사용 -> {BACKUP}")


# ============================================================
# 3. save_gold_prediction() 메서드 추가
# ============================================================
save_method = '''
    def save_gold_prediction(
        self,
        symbol: str,
        horizon: str,
        predicted_price: Decimal,
        predicted_at: datetime,
        target_timestamp: datetime,
        recommendation: str | None = None,
        confidence: str | None = None,
        training_mode: str | None = None,
    ) -> None:
        db = self.db_session_factory()

        try:
            crud.create_gold_prediction(
                db,
                symbol=symbol,
                horizon=horizon,
                predicted_price=predicted_price,
                predicted_at=predicted_at,
                target_timestamp=target_timestamp,
                recommendation=recommendation,
                confidence=confidence,
                training_mode=training_mode,
            )
        finally:
            db.close()

'''


if not has_save_method:

    # save_market_gap 함수의 "def" 위치를 정규식으로 찾음
    marker = "    def save_market_gap"

    marker_pos = text.find(marker)

    if marker_pos == -1:

        # save_market_gap이 없으면 load_saved_history 앞에 삽입
        marker = "    def load_saved_history"
        marker_pos = text.find(marker)

        if marker_pos == -1:
            print("ERROR: save_market_gap() 또는 load_saved_history() 위치를 찾지 못했습니다.")
            print("app/market.py 구조를 확인해주세요.")
            sys.exit(1)

        text = (
            text[:marker_pos]
            + save_method
            + text[marker_pos:]
        )

    else:

        text = (
            text[:marker_pos]
            + save_method
            + text[marker_pos:]
        )

    print("OK: save_gold_prediction() 추가 완료")


# ============================================================
# 4. 예측 DB 저장 코드
# ============================================================
prediction_block = '''
        # --------------------------------------------------------
        # 단기 / 중기 / 장기 예측 결과 DB 저장
        # --------------------------------------------------------
        if history:
            prediction_at = history[-1].timestamp

            for horizon_key in ("short", "medium", "long"):
                horizon_data = multi_prediction.get(
                    horizon_key,
                    {},
                )

                if not isinstance(horizon_data, dict):
                    continue

                forecast_price = horizon_data.get(
                    "predicted_price"
                )

                if forecast_price is None:
                    continue

                try:
                    forecast_price_decimal = Decimal(
                        str(forecast_price)
                    )

                    hours = float(
                        horizon_data.get("hours", 0)
                    )

                    if hours <= 0:
                        continue

                    target_timestamp = (
                        prediction_at
                        + timedelta(hours=hours)
                    )

                    self.save_gold_prediction(
                        symbol=prediction_symbol,
                        horizon=horizon_key,
                        predicted_price=forecast_price_decimal,
                        predicted_at=prediction_at,
                        target_timestamp=target_timestamp,
                        recommendation=horizon_data.get(
                            "recommendation",
                            "HOLD",
                        ),
                        confidence=horizon_data.get(
                            "confidence",
                            "LOW",
                        ),
                        training_mode=horizon_data.get(
                            "training_mode"
                        ),
                    )

                    print(
                        "GOLD PREDICTION SAVED:",
                        horizon_key,
                        forecast_price_decimal,
                        prediction_at,
                        target_timestamp,
                    )

                except Exception as exc:
                    logging.exception(
                        "Gold prediction DB 저장 실패: "
                        "horizon=%s error=%s",
                        horizon_key,
                        exc,
                    )

'''


if not has_save_logic:

    marker = "        short_prediction = multi_prediction.get"

    marker_pos = text.find(marker)

    if marker_pos == -1:
        print("ERROR: short_prediction 위치를 찾지 못했습니다.")
        print("multi_prediction 호출 주변 코드를 확인해주세요.")
        sys.exit(1)

    text = (
        text[:marker_pos]
        + prediction_block
        + text[marker_pos:]
    )

    print("OK: 예측 DB 저장 로직 추가 완료")


# ============================================================
# 5. 파일 저장
# ============================================================
TARGET.write_text(
    text,
    encoding="utf-8",
)


# ============================================================
# 6. Python 문법 검사
# ============================================================
print()
print("Python 문법 검사 중...")

try:
    py_compile.compile(
        str(TARGET),
        doraise=True,
    )
except Exception as exc:

    print()
    print("ERROR: 문법 검사 실패")
    print(exc)
    print()

    print("원본 복구:")
    print(f"cp {BACKUP} {TARGET}")

    sys.exit(1)


# ============================================================
# 7. 결과
# ============================================================
print()
print("==========================================")
print("OK: GOLD 예측 DB 저장 패치 완료")
print("==========================================")
print()
print(f"수정 파일 : {TARGET}")
print(f"백업 파일 : {BACKUP}")
print()
print("확인:")
print("grep -n -A35 'def save_gold_prediction' app/market.py")
print()
print("grep -n -A70 'GOLD PREDICTION SAVED' app/market.py")
print()
