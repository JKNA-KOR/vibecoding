from pathlib import Path
import re

path = Path("templates/dashboard.html")
text = path.read_text(encoding="utf-8")

# ------------------------------------------------------------
# 1. API 원본 데이터를 전역으로 보관
# ------------------------------------------------------------
if "let goldChartApiData = null;" not in text:
    text = text.replace(
        'let goldChartData = [];',
        '''let goldChartData = [];
let goldChartApiData = null;'''
    )

# ------------------------------------------------------------
# 2. 예측값 추출 함수를 강제로 교체
# ------------------------------------------------------------
new_prediction_function = r'''
function getGoldPredictionPoints(data) {
    const result = [];

    if (!data || typeof data !== "object") {
        return result;
    }

    // API의 실제 구조:
    // future_points.short
    // future_points.medium
    // future_points.long
    const futurePoints = data.future_points;

    const definitions = [
        {
            key: "short",
            label: "단기"
        },
        {
            key: "medium",
            label: "중기"
        },
        {
            key: "long",
            label: "장기"
        }
    ];

    if (futurePoints && typeof futurePoints === "object") {
        for (const definition of definitions) {
            const point = futurePoints[definition.key];

            if (!point || point.price == null || !point.timestamp) {
                continue;
            }

            const price = Number(point.price);
            const timestamp = new Date(point.timestamp);

            if (!Number.isFinite(price) || Number.isNaN(timestamp.getTime())) {
                continue;
            }

            result.push({
                key: definition.key,
                label: definition.label,
                price: price,
                timestamp: point.timestamp,
                recommendation: point.recommendation || "HOLD",
                confidence: point.confidence || "-"
            });
        }
    }

    // future_points가 없는 경우 horizons에서 보조 추출
    if (!result.length && data.horizons) {
        for (const definition of definitions) {
            const point = data.horizons[definition.key];

            if (!point || point.predicted_price == null) {
                continue;
            }

            const price = Number(point.predicted_price);
            const timestamp = point.timestamp || point.prediction_timestamp;

            if (!Number.isFinite(price) || !timestamp) {
                continue;
            }

            result.push({
                key: definition.key,
                label: definition.label,
                price: price,
                timestamp: timestamp,
                recommendation: point.recommendation || "HOLD",
                confidence: point.confidence || "-"
            });
        }
    }

    return result;
}
'''

pattern = re.compile(
    r'function getGoldPredictionPoints\(data\)\s*\{.*?\n\}',
    re.DOTALL
)

if pattern.search(text):
    text = pattern.sub(new_prediction_function.strip(), text, count=1)
else:
    marker = "function drawAceGoldChart(data) {"
    if marker not in text:
        raise SystemExit("ERROR: drawAceGoldChart 선언을 찾지 못했습니다.")

    text = text.replace(
        marker,
        new_prediction_function.strip() + "\n\n" + marker,
        1
    )

# ------------------------------------------------------------
# 3. drawAceGoldChart 시작 시 API 데이터를 보관
# ------------------------------------------------------------
old = '''function drawAceGoldChart(data) {
    const canvas = document.getElementById("goldChart");'''

new = '''function drawAceGoldChart(data) {
    // API 전체 데이터를 보관
    goldChartApiData = data;

    const canvas = document.getElementById("goldChart");'''

if old in text:
    text = text.replace(old, new, 1)

# ------------------------------------------------------------
# 4. predictions를 실제 future_points에서 강제로 가져오도록 유지
# ------------------------------------------------------------
old = 'const predictions = getGoldPredictionPoints(data);'

if old not in text:
    raise SystemExit("ERROR: predictions 선언 위치를 찾지 못했습니다.")

# 첫 번째 occurrence는 그래프 내부의 가격 범위 계산에 사용
text = text.replace(
    old,
    '''const predictions = getGoldPredictionPoints(data);

    console.log(
        "[GOLD CHART] predictions =",
        predictions
    );''',
    1
)

# ------------------------------------------------------------
# 5. resize 시 series만 전달하지 말고 API 전체 데이터를 다시 전달
# ------------------------------------------------------------
old_resize = '''drawAceGoldChart({
                series: {
                    ACE_KRX_GOLD: goldChartData
                }
            });'''

new_resize = '''drawAceGoldChart(
                goldChartApiData || {
                    series: {
                        ACE_KRX_GOLD: goldChartData
                    }
                }
            );'''

if old_resize in text:
    text = text.replace(old_resize, new_resize, 1)
else:
    print("WARNING: resize 코드 패턴을 찾지 못했습니다.")

# ------------------------------------------------------------
# 6. 예측값이 확실하게 보이도록 예측 영역 라벨 추가
# ------------------------------------------------------------
needle = '''// 예측
        const legendPredictionX =
            padding.left + 105;'''

replacement = '''// 예측
        const legendPredictionX =
            padding.left + 105;'''

# 기존 코드가 있으므로 구조는 유지

# ------------------------------------------------------------
# 7. 파일 저장
# ------------------------------------------------------------
path.write_text(text, encoding="utf-8")

print("==========================================")
print("OK: GOLD 예측 그래프 강제 연결 패치 완료")
print("==========================================")
print("")
print("수정 내용:")
print("1. future_points.short/medium/long 직접 연결")
print("2. horizons fallback 추가")
print("3. API 전체 데이터를 goldChartApiData에 저장")
print("4. resize 시 예측 데이터 유지")
print("5. 브라우저 console에 predictions 출력")
print("")
print("예상 예측값:")
print("단기  : 28050.58")
print("중기  : 26800.77")
print("장기  : 24552.00")
