from pathlib import Path
import shutil
import sys

path = Path("templates/dashboard.html")
backup = Path("templates/dashboard.html.before_prediction")

if not path.exists():
    print(f"[ERROR] {path} 파일이 없습니다.")
    sys.exit(1)

original = path.read_text(encoding="utf-8")

# 백업
shutil.copy2(path, backup)
print(f"[OK] 백업 생성: {backup}")

content = original

# ------------------------------------------------------------
# 1. 예측 데이터 추출 함수
# ------------------------------------------------------------

prediction_js = r'''
function getGoldPredictionPoints(data) {
    const points = data?.future_points;

    if (!points || typeof points !== "object") {
        return [];
    }

    const order = ["short", "medium", "long"];

    return order
        .map(key => {
            const item = points[key];

            if (!item || item.price == null || !item.timestamp) {
                return null;
            }

            const price = Number(item.price);

            if (!Number.isFinite(price)) {
                return null;
            }

            return {
                key,
                label:
                    item.label ||
                    (
                        key === "short"
                            ? "단기"
                            : key === "medium"
                                ? "중기"
                                : "장기"
                    ),
                price,
                timestamp: item.timestamp,
                recommendation: item.recommendation || "HOLD",
                confidence: item.confidence || "-"
            };
        })
        .filter(Boolean);
}
'''

marker = '// ------------------------------------------------------------\n// ACE KRX금현물 시세 추세 그래프'

if "function getGoldPredictionPoints(data)" not in content:
    if marker not in content:
        print("[ERROR] 그래프 JavaScript 영역을 찾을 수 없습니다.")
        sys.exit(1)

    content = content.replace(
        marker,
        prediction_js + "\n" + marker,
        1
    )

    print("[OK] 예측 데이터 함수 추가")

# ------------------------------------------------------------
# 2. drawAceGoldChart 함수 전체를 확장하기 위해
#    기존 함수 마지막 부분에 예측선 코드를 삽입
# ------------------------------------------------------------

prediction_draw = r'''
    // --------------------------------------------------------
    // 단기 / 중기 / 장기 예측선
    // --------------------------------------------------------
    const predictions = getGoldPredictionPoints(data);

    if (predictions.length && series.length) {
        const actualLatest = series[series.length - 1];

        const actualTime =
            new Date(actualLatest.timestamp).getTime();

        const actualPrice =
            actualLatest.price;

        // 실제 마지막 시점 + 예측 시점을 하나의 시간축으로 구성
        const forecastPoints = [
            {
                label: "현재",
                timestamp: actualLatest.timestamp,
                price: actualPrice,
                type: "actual"
            },
            ...predictions.map(item => ({
                label: item.label,
                timestamp: item.timestamp,
                price: item.price,
                type: "prediction",
                recommendation: item.recommendation,
                confidence: item.confidence
            }))
        ];

        const forecastTimes = forecastPoints.map(item =>
            new Date(item.timestamp).getTime()
        );

        const forecastMinTime =
            Math.min(...forecastTimes);

        const forecastMaxTime =
            Math.max(...forecastTimes);

        // 기존 그래프 영역의 오른쪽에 예측 구간을 추가
        const predictionStartX =
            padding.left + chartWidth * 0.76;

        const predictionEndX =
            width - padding.right;

        const timeRange =
            forecastMaxTime - forecastMinTime;

        const forecastX = timestamp => {
            if (!timeRange) {
                return predictionStartX;
            }

            return predictionStartX +
                (
                    (timestamp - forecastMinTime) /
                    timeRange
                ) *
                (predictionEndX - predictionStartX);
        };

        // 예측선
        ctx.beginPath();

        forecastPoints.forEach((point, index) => {
            const timestamp =
                new Date(point.timestamp).getTime();

            let xx;

            if (index === 0) {
                xx = predictionStartX;
            } else {
                xx = forecastX(timestamp);
            }

            const yy = y(point.price);

            if (index === 0) {
                ctx.moveTo(xx, yy);
            } else {
                ctx.lineTo(xx, yy);
            }
        });

        ctx.setLineDash([7, 5]);
        ctx.strokeStyle = "#f59e0b";
        ctx.lineWidth = 2.5;
        ctx.lineJoin = "round";
        ctx.lineCap = "round";
        ctx.stroke();
        ctx.setLineDash([]);

        // 예측 포인트
        forecastPoints.slice(1).forEach(point => {
            const timestamp =
                new Date(point.timestamp).getTime();

            const xx = forecastX(timestamp);
            const yy = y(point.price);

            ctx.beginPath();
            ctx.arc(xx, yy, 5, 0, Math.PI * 2);

            ctx.fillStyle =
                point.recommendation === "BUY"
                    ? "#16a34a"
                    : point.recommendation === "SELL"
                        ? "#dc2626"
                        : "#6b7280";

            ctx.fill();

            // 예측 라벨
            ctx.font =
                "bold 12px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";

            ctx.textAlign = "center";
            ctx.textBaseline = "bottom";

            ctx.fillStyle = "#172033";

            ctx.fillText(
                `${point.label} ${point.price.toLocaleString("ko-KR")}원`,
                xx,
                yy - 10
            );
        });

        // 현재 → 예측 구간 배경 경계 표시
        const latestActualX =
            predictionStartX;

        ctx.beginPath();
        ctx.moveTo(latestActualX, padding.top);
        ctx.lineTo(latestActualX, height - padding.bottom);

        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = "#d0d5dd";
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.setLineDash([]);

        // "예측" 표시
        ctx.font =
            "12px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";

        ctx.textAlign = "left";
        ctx.textBaseline = "top";

        ctx.fillStyle = "#667085";

        ctx.fillText(
            "예측",
            latestActualX + 8,
            padding.top + 4
        );

        // 범례
        const legendY = 12;

        ctx.textAlign = "left";
        ctx.textBaseline = "middle";

        // 실제
        ctx.beginPath();
        ctx.moveTo(padding.left, legendY);
        ctx.lineTo(padding.left + 22, legendY);

        ctx.strokeStyle = "#2563eb";
        ctx.lineWidth = 2.5;
        ctx.stroke();

        ctx.fillStyle = "#667085";
        ctx.fillText(
            "실제 시세",
            padding.left + 30,
            legendY
        );

        // 예측
        const legendPredictionX =
            padding.left + 105;

        ctx.beginPath();
        ctx.moveTo(legendPredictionX, legendY);
        ctx.lineTo(legendPredictionX + 22, legendY);

        ctx.setLineDash([5, 4]);
        ctx.strokeStyle = "#f59e0b";
        ctx.lineWidth = 2.5;
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = "#667085";
        ctx.fillText(
            "예측",
            legendPredictionX + 30,
            legendY
        );
    }
'''

# drawAceGoldChart 함수 내부에서
# "정보" 영역 바로 앞에 삽입
info_marker = '''    // --------------------------------------------------------
    // 정보
    // --------------------------------------------------------'''

if "const predictions = getGoldPredictionPoints(data);" not in content:
    if info_marker not in content:
        print("[ERROR] 그래프 정보 영역을 찾을 수 없습니다.")
        sys.exit(1)

    content = content.replace(
        info_marker,
        prediction_draw + "\n" + info_marker,
        1
    )

    print("[OK] 단기/중기/장기 예측선 추가")

# ------------------------------------------------------------
# 3. 그래프 정보 표시 개선
# ------------------------------------------------------------

old_info = '''    if (info) {
        info.textContent =
            `${series.length.toLocaleString("ko-KR")}개 데이터 · ` +
            `최근 ${latest.price.toLocaleString("ko-KR")}원 · ` +
            `${formatChartDateTime(latest.timestamp)}`;
    }'''

new_info = '''    if (info) {
        const predictionSummary = predictions?.length
            ? ` · 단기 ${predictions[0].price.toLocaleString("ko-KR")}원 · ` +
              `중기 ${predictions[1]?.price.toLocaleString("ko-KR") ?? "-"}원 · ` +
              `장기 ${predictions[2]?.price.toLocaleString("ko-KR") ?? "-"}원`
            : "";

        info.textContent =
            `${series.length.toLocaleString("ko-KR")}개 데이터 · ` +
            `최근 ${latest.price.toLocaleString("ko-KR")}원` +
            predictionSummary;
    }'''

if old_info in content:
    content = content.replace(old_info, new_info, 1)
    print("[OK] 그래프 정보 표시 개선")

# ------------------------------------------------------------
# 4. 저장
# ------------------------------------------------------------

if content == original:
    print("[WARNING] 변경사항이 없습니다.")
    sys.exit(0)

path.write_text(content, encoding="utf-8")

print()
print("=" * 60)
print("[SUCCESS] 예측 그래프 패치 완료")
print("=" * 60)
print(f"백업: {backup}")
print(f"수정: {path}")
print()
print("확인:")
print("  grep -n 'getGoldPredictionPoints\\|const predictions' templates/dashboard.html")
print("  git diff -- templates/dashboard.html")
