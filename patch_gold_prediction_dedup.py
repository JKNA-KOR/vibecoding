from pathlib import Path
import shutil

MARKET = Path("app/market.py")
CRUD = Path("app/crud.py")

market_backup = MARKET.with_name("market.py.before_gold_prediction_dedup")
crud_backup = CRUD.with_name("crud.py.before_gold_prediction_dedup")

# ------------------------------------------------------------
# Backup
# ------------------------------------------------------------
if not market_backup.exists():
    shutil.copy2(MARKET, market_backup)
    print(f"[OK] market.py 백업: {market_backup}")
else:
    print(f"[INFO] 기존 market.py 백업 사용: {market_backup}")

if not crud_backup.exists():
    shutil.copy2(CRUD, crud_backup)
    print(f"[OK] crud.py 백업: {crud_backup}")
else:
    print(f"[INFO] 기존 crud.py 백업 사용: {crud_backup}")

crud_text = CRUD.read_text(encoding="utf-8")
market_text = MARKET.read_text(encoding="utf-8")

# ------------------------------------------------------------
# 1. crud.py에 중복 조회 함수 추가
# ------------------------------------------------------------
marker = "\ndef list_gold_predictions(\n"

if "def find_gold_prediction(" not in crud_text:
    find_method = '''
def find_gold_prediction(
    db: Session,
    symbol: str,
    horizon: str,
    predicted_at: datetime,
    target_timestamp: datetime,
) -> Optional[models.GoldPrediction]:
    return db.execute(
        select(models.GoldPrediction)
        .where(
            models.GoldPrediction.symbol == symbol,
            models.GoldPrediction.horizon == horizon,
            models.GoldPrediction.predicted_at == predicted_at,
            models.GoldPrediction.target_timestamp == target_timestamp,
        )
        .limit(1)
    ).scalar_one_or_none()


'''

    if marker not in crud_text:
        raise SystemExit(
            "[ERROR] crud.py에서 list_gold_predictions() 위치를 찾지 못했습니다."
        )

    crud_text = crud_text.replace(
        marker,
        "\n" + find_method + "def list_gold_predictions(\n",
        1,
    )

    CRUD.write_text(crud_text, encoding="utf-8")
    print("[OK] crud.py에 find_gold_prediction() 추가")
else:
    print("[INFO] find_gold_prediction() 이미 존재합니다.")

# ------------------------------------------------------------
# 2. market.py save_gold_prediction() 교체
# ------------------------------------------------------------
old = '''    def save_gold_prediction(
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

new = '''    def save_gold_prediction(
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
            # ----------------------------------------------------
            # 동일 예측 중복 저장 방지
            #
            # 같은 symbol + horizon + predicted_at +
            # target_timestamp는 동일한 하나의 예측으로 간주한다.
            # ----------------------------------------------------
            existing = crud.find_gold_prediction(
                db,
                symbol=symbol,
                horizon=horizon,
                predicted_at=predicted_at,
                target_timestamp=target_timestamp,
            )

            if existing is not None:
                logging.info(
                    "GOLD PREDICTION SKIP DUPLICATE: "
                    "symbol=%s horizon=%s predicted_at=%s "
                    "target=%s price=%s",
                    symbol,
                    horizon,
                    predicted_at,
                    target_timestamp,
                    existing.predicted_price,
                )
                return

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

            logging.info(
                "GOLD PREDICTION SAVED: "
                "symbol=%s horizon=%s price=%s "
                "predicted_at=%s target=%s",
                symbol,
                horizon,
                predicted_price,
                predicted_at,
                target_timestamp,
            )

        finally:
            db.close()
'''

if old in market_text:
    market_text = market_text.replace(old, new, 1)
    MARKET.write_text(market_text, encoding="utf-8")
    print("[OK] market.py save_gold_prediction() 중복 방지 적용")
elif "GOLD PREDICTION SKIP DUPLICATE" in market_text:
    print("[INFO] market.py 중복 방지 로직이 이미 적용되어 있습니다.")
else:
    raise SystemExit(
        "[ERROR] market.py의 save_gold_prediction() 원본을 찾지 못했습니다."
    )

print()
print("=" * 60)
print("[SUCCESS] Gold prediction 중복 저장 방지 패치 완료")
print("=" * 60)
print()
print("확인:")
print("  grep -n -A55 'def save_gold_prediction' app/market.py")
print("  grep -n -A20 'def find_gold_prediction' app/crud.py")
print()
print("문법 검사:")
print("  python3 -m py_compile app/market.py app/crud.py")
