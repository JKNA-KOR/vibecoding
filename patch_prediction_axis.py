from pathlib import Path
import shutil
import re
import sys


BASE_DIR = Path(__file__).resolve().parent
HTML_FILE = BASE_DIR / "templates" / "dashboard.html"
BACKUP_FILE = BASE_DIR / "templates" / "dashboard.html.before_prediction_axis"


OLD_PATTERN = re.compile(
    r"""function getPredictionSeries\(data\) \{.*?\n\}""",
    re.DOTALL,
)


NEW_FUNCTION = r'''function getPredictionSeries(data) {
    const source = data?.prediction_series;

    const result = {
        short: [],
        medium: [],
        long: []
    };

    if (!source || typeof source !== "object") {
        return result;
    }

    for (const horizon of ["short", "medium", "long"]) {
        const rows = source[horizon];

        if (!Array.isArray(rows)) {
            continue;
        }

        result[horizon] = rows
            .filter(item =>
                item &&
                (item.predicted_at || item.timestamp) &&
                item.price != null &&
                Number.isFinite(Number(item.price))
            )
            .map(item => ({
                /*
                 * ----------------------------------------------------
                 * 중요
                 *
                 * 그래프의 X축은 target_timestamp가 아니라
                 * predicted_at을 사용한다.
                 *
                 * predicted_at:
                 *   모델이 예측을 생성한 시점
                 *
                 * target_timestamp:
                 *   모델이 예측한 미래 시점
                 *
                 * 이 그래프의 목적은
                 * "그 당시 모델이 무엇을 예측했는가"
                 * 를 보는 것이므로 predicted_at 기준으로 표시한다.
                 * ----------------------------------------------------
                 */
                timestamp: item.predicted_at || item.timestamp,

                predicted_at:
                    item.predicted_at || item.timestamp,

                target_timestamp:
                    item.target_timestamp || null,

                price: Number(item.price),

                recommendation:
                    item.recommendation || "",

                confidence:
                    item.confidence || "",

                training_mode:
                    item.training_mode || ""
            }))
            .sort((a, b) =>
                new Date(a.timestamp) - new Date(b.timestamp)
            );
    }

    return result;
}'''


def main():
    print("=" * 60)
    print("Prediction Graph X-Axis Patch")
    print("=" * 60)

    if not HTML_FILE.exists():
        print(f"[ERROR] 파일을 찾을 수 없습니다: {HTML_FILE}")
        sys.exit(1)

    content = HTML_FILE.read_text(encoding="utf-8")

    # ------------------------------------------------------------
    # 현재 함수 개수 확인
    # ------------------------------------------------------------
    matches = OLD_PATTERN.findall(content)

    print(f"[INFO] getPredictionSeries 발견: {len(matches)}개")

    if len(matches) == 0:
        print("[ERROR] getPredictionSeries 함수를 찾지 못했습니다.")
        sys.exit(1)

    if len(matches) > 1:
        print("[ERROR] getPredictionSeries 함수가 2개 이상 존재합니다.")
        print("먼저 dashboard.html의 중복 JavaScript를 정리해야 합니다.")
        sys.exit(1)

    old_function = matches[0]

    # ------------------------------------------------------------
    # 이미 변경되어 있는지 확인
    # ------------------------------------------------------------
    if (
        "timestamp: item.predicted_at || item.timestamp" in old_function
        and "target_timestamp" in old_function
    ):
        print("[INFO] 이미 predicted_at 기준으로 설정되어 있습니다.")
        print("[INFO] 변경사항이 없습니다.")
        return

    # ------------------------------------------------------------
    # 백업
    # ------------------------------------------------------------
    if not BACKUP_FILE.exists():
        shutil.copy2(HTML_FILE, BACKUP_FILE)
        print(f"[OK] 백업 생성: {BACKUP_FILE}")
    else:
        print(f"[INFO] 기존 백업 사용: {BACKUP_FILE}")

    # ------------------------------------------------------------
    # 함수 교체
    # ------------------------------------------------------------
    new_content = content.replace(
        old_function,
        NEW_FUNCTION,
        1,
    )

    if new_content == content:
        print("[ERROR] HTML 변경에 실패했습니다.")
        sys.exit(1)

    HTML_FILE.write_text(
        new_content,
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print("[SUCCESS] 그래프 X축 기준 변경 완료")
    print("=" * 60)

    print()
    print("변경 내용:")
    print("  기존 X축 : target_timestamp")
    print("  변경 X축 : predicted_at")

    print()
    print("그래프 의미:")
    print("  실제 가격       → 실제 측정 시점")
    print("  단기 3시간      → 예측을 생성한 시점")
    print("  중기 3일        → 예측을 생성한 시점")
    print("  장기 30일       → 예측을 생성한 시점")

    print()
    print("보존되는 데이터:")
    print("  predicted_at")
    print("  target_timestamp")
    print("  predicted_price")
    print("  recommendation")
    print("  confidence")
    print("  training_mode")

    print()
    print(f"백업 파일:")
    print(f"  {BACKUP_FILE}")

    print()
    print("확인 명령:")
    print("  grep -n -A65 'function getPredictionSeries' templates/dashboard.html")
    print()
    print("변경사항:")
    print("  git diff -- templates/dashboard.html")


if __name__ == "__main__":
    main()