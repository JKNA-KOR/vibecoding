from pathlib import Path
import re
import shutil
import sys

HTML = Path("templates/dashboard.html")
BACKUP = Path("templates/dashboard.html.before_prediction_timestamp")

if not HTML.exists():
    print(f"[ERROR] 파일이 없습니다: {HTML}")
    sys.exit(1)

content = HTML.read_text(encoding="utf-8")

# ------------------------------------------------------------
# 백업
# ------------------------------------------------------------
if not BACKUP.exists():
    shutil.copy2(HTML, BACKUP)
    print(f"[OK] 백업 생성 -> {BACKUP}")
else:
    print(f"[INFO] 기존 백업 사용 -> {BACKUP}")


# ------------------------------------------------------------
# getPredictionSeries 함수
#
# 핵심:
#
# predicted_at
#   = 모델이 실제 예측을 생성한 시점
#
# target_timestamp
#   = 모델이 예측한 미래 시점
#
# 그래프에서는 predicted_at을 X축으로 사용한다.
# ------------------------------------------------------------
new_function = r'''
function getPredictionSeries(data) {
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
                item.predicted_at &&
                item.price != null &&
                Number.isFinite(Number(item.price))
            )
            .map(item => ({
                /*
                 * ====================================================
                 * 중요
                 *
                 * X축은 target_timestamp가 아니다.
                 *
                 * predicted_at = 모델이 예측을 생성한 시점
                 * target_timestamp = 모델이 예측한 미래 시점
                 *
                 * 그래프에서는 "그 시점에 모델이 무엇을
                 * 예측했는가"를 보여주기 위해 predicted_at을
                 * timestamp로 사용한다.
                 * ====================================================
                 */
                timestamp: item.predicted_at,

                predicted_at: item.predicted_at,

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
                new Date(a.timestamp) -
                new Date(b.timestamp)
            );
    }

    return result;
}
'''.strip()


# ------------------------------------------------------------
# 기존 함수 전체 교체
# ------------------------------------------------------------
pattern = re.compile(
    r'function getPredictionSeries\(data\)\s*\{.*?\n\}',
    re.DOTALL,
)

matches = list(pattern.finditer(content))

if len(matches) != 1:
    print(
        f"[ERROR] getPredictionSeries 함수 개수가 예상과 다릅니다: "
        f"{len(matches)}개"
    )
    sys.exit(1)

content = (
    content[:matches[0].start()]
    + new_function
    + content[matches[0].end():]
)

print("[OK] getPredictionSeries 교체 완료")


# ------------------------------------------------------------
# drawPredictionLine 확인
#
# 예측선 역시 timestamp를 사용하도록 확인한다.
# ------------------------------------------------------------
draw_match = re.search(
    r'function drawPredictionLine\s*\(',
    content,
)

if not draw_match:
    print("[ERROR] drawPredictionLine 함수를 찾을 수 없습니다.")
    sys.exit(1)

print("[OK] drawPredictionLine 확인")


# ------------------------------------------------------------
# drawAceGoldChart에서 predictionSeries 사용 확인
# ------------------------------------------------------------
chart_match = re.search(
    r'function drawAceGoldChart\s*\(',
    content,
)

if not chart_match:
    print("[ERROR] drawAceGoldChart 함수를 찾을 수 없습니다.")
    sys.exit(1)

print("[OK] drawAceGoldChart 확인")


# ------------------------------------------------------------
# 저장
# ------------------------------------------------------------
HTML.write_text(content, encoding="utf-8")

print()
print("=" * 60)
print("[SUCCESS] 예측 시점 기준 그래프 패치 완료")
print("=" * 60)

print()
print("그래프 기준:")
print("  실제 가격       -> 실제 timestamp")
print("  단기 3시간 예측 -> predicted_at")
print("  중기 3일 예측   -> predicted_at")
print("  장기 30일 예측  -> predicted_at")
print()
print("target_timestamp는 그래프 X축에 사용하지 않습니다.")
print()
print("백업:")
print(f"  {BACKUP}")
print()
print("확인 명령:")
print("  grep -n -A70 'function getPredictionSeries' templates/dashboard.html")
print("  grep -n 'function drawPredictionLine' templates/dashboard.html")
print("  grep -n 'function drawAceGoldChart' templates/dashboard.html")
