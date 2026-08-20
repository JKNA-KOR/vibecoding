from pathlib import Path
import re
import shutil
import subprocess
import sys

HTML = Path("templates/dashboard.html")
BACKUP = Path("templates/dashboard.html.before_prediction_trend_v2")

if not HTML.exists():
    print(f"[ERROR] {HTML} 파일을 찾을 수 없습니다.")
    sys.exit(1)

content = HTML.read_text(encoding="utf-8")

if not BACKUP.exists():
    shutil.copy2(HTML, BACKUP)
    print(f"[OK] 백업 생성 -> {BACKUP}")
else:
    print(f"[INFO] 기존 백업 사용 -> {BACKUP}")

# ------------------------------------------------------------
# 기존 그래프 영역
#
# getPredictionSeries()부터 resize 이벤트 끝까지 교체한다.
# render(d) 자체는 절대 건드리지 않는다.
# ------------------------------------------------------------
start_marker = "function getPredictionSeries(data) {"
end_marker = "function render(d){"

start = content.find(start_marker)
end = content.find(end_marker)

if start < 0:
    print("[ERROR] getPredictionSeries() 시작 위치를 찾지 못했습니다.")
    sys.exit(1)

if end < 0:
    print("[ERROR] render(d) 시작 위치를 찾지 못했습니다.")
    sys.exit(1)

if end <= start:
    print("[ERROR] 그래프 영역의 시작/끝 위치가 잘못되었습니다.")
    sys.exit(1)

new_chart_js = r'''
// ============================================================
// ACE KRX금현물 + 과거/현재 예측 추세 그래프
//
// 선 1 : 실제 ACE KRX금현물
// 선 2 : 단기 3시간 예측
// 선 3 : 중기 3일 예측
// 선 4 : 장기 30일 예측
//
// 예측 데이터는 반드시 target_timestamp에 표시한다.
// 즉, "언제 예측했는가"가 아니라
// "언제의 가격을 예측했는가"를 X축에 표시한다.
// ============================================================

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
                item.target_timestamp &&
                item.price != null &&
                Number.isFinite(Number(item.price))
            )
            .map(item => ({
                timestamp: item.target_timestamp,
                predicted_at: item.predicted_at || item.timestamp || null,
                price: Number(item.price),
                recommendation: item.recommendation || "",
                confidence: item.confidence || "",
                training_mode: item.training_mode || ""
            }))
            .filter(item => {
                const t = new Date(item.timestamp).getTime();
                return Number.isFinite(t);
            })
            .sort((a, b) =>
                new Date(a.timestamp).getTime() -
                new Date(b.timestamp).getTime()
            );
    }

    return result;
}


// ------------------------------------------------------------
// 실제 ACE KRX금현물
// ------------------------------------------------------------
function getAceGoldSeries(data) {
    const source = data?.series?.ACE_KRX_GOLD;

    if (!Array.isArray(source)) {
        return [];
    }

    return source
        .filter(item =>
            item &&
            item.timestamp &&
            item.price != null &&
            Number.isFinite(Number(item.price))
        )
        .map(item => ({
            timestamp: item.timestamp,
            price: Number(item.price)
        }))
        .filter(item =>
            Number.isFinite(new Date(item.timestamp).getTime())
        )
        .sort((a, b) =>
            new Date(a.timestamp).getTime() -
            new Date(b.timestamp).getTime()
        );
}


// ------------------------------------------------------------
// 날짜 포맷
// ------------------------------------------------------------
function formatChartTime(timestamp) {
    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
        return "";
    }

    return date.toLocaleTimeString("ko-KR", {
        hour: "2-digit",
        minute: "2-digit"
    });
}


function formatChartDateTime(timestamp) {
    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
        return "";
    }

    return date.toLocaleString("ko-KR", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false
    });
}


// ------------------------------------------------------------
// 모든 가격
// ------------------------------------------------------------
function getAllChartPrices(actual, predictions) {
    const prices = [];

    actual.forEach(item => {
        if (Number.isFinite(item.price)) {
            prices.push(item.price);
        }
    });

    ["short", "medium", "long"].forEach(horizon => {
        (predictions[horizon] || []).forEach(item => {
            if (Number.isFinite(item.price)) {
                prices.push(item.price);
            }
        });
    });

    return prices;
}


// ------------------------------------------------------------
// 예측선 그리기
//
// 각 예측값을 target_timestamp 위치에 찍는다.
//
// 중요한 차이:
// 과거 예측도 그대로 연결한다.
// 따라서 DB에 저장된 예측값들이 시간 순서대로
// 하나의 "예측 추세선"을 형성한다.
// ------------------------------------------------------------
function drawPredictionLine(
    ctx,
    points,
    x,
    y,
    color,
    lineWidth
) {
    if (!Array.isArray(points) || !points.length) {
        return;
    }

    ctx.beginPath();

    let started = false;

    for (const item of points) {
        const timestamp = new Date(item.timestamp).getTime();

        if (!Number.isFinite(timestamp)) {
            continue;
        }

        const xx = x(timestamp);
        const yy = y(item.price);

        if (!started) {
            ctx.moveTo(xx, yy);
            started = true;
        } else {
            ctx.lineTo(xx, yy);
        }
    }

    if (!started) {
        return;
    }

    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.stroke();
}


// ------------------------------------------------------------
// 예측 포인트 표시
//
// 예측값 하나하나를 작은 점으로 표시해서
// 실제 DB에 저장된 예측값의 위치를 명확하게 보여준다.
// ------------------------------------------------------------
function drawPredictionPoints(
    ctx,
    points,
    x,
    y,
    color
) {
    if (!Array.isArray(points)) {
        return;
    }

    points.forEach(item => {
        const timestamp = new Date(item.timestamp).getTime();

        if (!Number.isFinite(timestamp)) {
            return;
        }

        const xx = x(timestamp);
        const yy = y(item.price);

        ctx.beginPath();
        ctx.arc(xx, yy, 3, 0, Math.PI * 2);

        ctx.fillStyle = color;
        ctx.fill();
    });
}


// ------------------------------------------------------------
// 메인 그래프
// ------------------------------------------------------------
function drawAceGoldChart(data) {
    const canvas = document.getElementById("goldChart");
    const empty = document.getElementById("goldChartEmpty");
    const info = document.getElementById("goldChartInfo");

    if (!canvas) {
        return;
    }

    const actualSeries = getAceGoldSeries(data);
    const predictionSeries = getPredictionSeries(data);

    goldChartData = actualSeries;
    goldPredictionData = predictionSeries;

    if (!actualSeries.length) {
        canvas.style.display = "none";

        if (empty) {
            empty.style.display = "flex";
        }

        if (info) {
            info.textContent = "실제 가격 데이터 없음";
        }

        return;
    }

    canvas.style.display = "block";

    if (empty) {
        empty.style.display = "none";
    }

    const container = canvas.parentElement;

    const width = container.clientWidth;
    const height = container.clientHeight;

    if (width <= 0 || height <= 0) {
        return;
    }

    const dpr = window.devicePixelRatio || 1;

    canvas.width = width * dpr;
    canvas.height = height * dpr;

    canvas.style.width = width + "px";
    canvas.style.height = height + "px";

    const ctx = canvas.getContext("2d");

    if (!ctx) {
        return;
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const padding = {
        top: 40,
        right: 35,
        bottom: 55,
        left: 78
    };

    const chartWidth =
        width - padding.left - padding.right;

    const chartHeight =
        height - padding.top - padding.bottom;

    if (chartWidth <= 0 || chartHeight <= 0) {
        return;
    }


    // ========================================================
    // 전체 시간 범위
    //
    // 실제 가격
    // +
    // 과거 예측
    // +
    // 미래 예측
    // 모두 포함한다.
    // ========================================================

    const allPoints = [];

    actualSeries.forEach(item => {
        allPoints.push(item);
    });

    ["short", "medium", "long"].forEach(horizon => {
        (predictionSeries[horizon] || []).forEach(item => {
            allPoints.push(item);
        });
    });

    const timestamps = allPoints
        .map(item => new Date(item.timestamp).getTime())
        .filter(value => Number.isFinite(value));

    if (!timestamps.length) {
        return;
    }

    let minTime = Math.min(...timestamps);
    let maxTime = Math.max(...timestamps);

    if (minTime === maxTime) {
        minTime -= 3600000;
        maxTime += 3600000;
    }

    const timeRange = maxTime - minTime;

    // 과거 쪽 여유
    minTime -= timeRange * 0.02;

    // 미래 예측을 볼 수 있도록 오른쪽 여유
    maxTime += timeRange * 0.05;


    // ========================================================
    // Y축
    // ========================================================

    const prices = getAllChartPrices(
        actualSeries,
        predictionSeries
    );

    if (!prices.length) {
        return;
    }

    let minPrice = Math.min(...prices);
    let maxPrice = Math.max(...prices);

    if (minPrice === maxPrice) {
        minPrice -= 10;
        maxPrice += 10;
    }

    const priceRange = maxPrice - minPrice;

    minPrice -= priceRange * 0.08;
    maxPrice += priceRange * 0.08;


    // ========================================================
    // 좌표 변환
    // ========================================================

    const x = timestamp => {
        const time =
            timestamp instanceof Date
                ? timestamp.getTime()
                : Number(timestamp);

        return padding.left +
            ((time - minTime) /
                (maxTime - minTime)) *
            chartWidth;
    };

    const y = price => {
        return padding.top +
            ((maxPrice - price) /
                (maxPrice - minPrice)) *
            chartHeight;
    };


    ctx.clearRect(0, 0, width, height);


    // ========================================================
    // Grid
    // ========================================================

    ctx.font =
        "12px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";

    ctx.textAlign = "right";
    ctx.textBaseline = "middle";

    const gridCount = 5;

    for (let i = 0; i <= gridCount; i++) {
        const ratio = i / gridCount;

        const price =
            maxPrice -
            ratio * (maxPrice - minPrice);

        const yy =
            padding.top +
            ratio * chartHeight;

        ctx.beginPath();
        ctx.moveTo(padding.left, yy);
        ctx.lineTo(width - padding.right, yy);

        ctx.strokeStyle = "#edf0f5";
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.fillStyle = "#667085";

        ctx.fillText(
            Math.round(price).toLocaleString("ko-KR"),
            padding.left - 10,
            yy
        );
    }


    // ========================================================
    // X축
    // ========================================================

    ctx.textAlign = "center";
    ctx.textBaseline = "top";

    const xLabelCount = 7;

    for (let i = 0; i < xLabelCount; i++) {
        const ratio =
            i / Math.max(1, xLabelCount - 1);

        const timestamp =
            minTime +
            ratio * (maxTime - minTime);

        const xx = x(timestamp);

        ctx.fillStyle = "#667085";

        ctx.fillText(
            formatChartDateTime(timestamp).slice(0, 16),
            xx,
            height - padding.bottom + 12
        );
    }


    // ========================================================
    // 실제 가격
    // ========================================================

    drawPredictionLine(
        ctx,
        actualSeries,
        x,
        y,
        "#2563eb",
        2.8
    );


    // ========================================================
    // 단기 예측
    // ========================================================

    drawPredictionLine(
        ctx,
        predictionSeries.short,
        x,
        y,
        "#f59e0b",
        2.2
    );

    drawPredictionPoints(
        ctx,
        predictionSeries.short,
        x,
        y,
        "#f59e0b"
    );


    // ========================================================
    // 중기 예측
    // ========================================================

    drawPredictionLine(
        ctx,
        predictionSeries.medium,
        x,
        y,
        "#16a34a",
        2.2
    );

    drawPredictionPoints(
        ctx,
        predictionSeries.medium,
        x,
        y,
        "#16a34a"
    );


    // ========================================================
    // 장기 예측
    // ========================================================

    drawPredictionLine(
        ctx,
        predictionSeries.long,
        x,
        y,
        "#9333ea",
        2.2
    );

    drawPredictionPoints(
        ctx,
        predictionSeries.long,
        x,
        y,
        "#9333ea"
    );


    // ========================================================
    // 실제 최신 가격
    // ========================================================

    const latest =
        actualSeries[actualSeries.length - 1];

    const latestX =
        x(new Date(latest.timestamp).getTime());

    const latestY =
        y(latest.price);

    ctx.beginPath();

    ctx.arc(
        latestX,
        latestY,
        5,
        0,
        Math.PI * 2
    );

    ctx.fillStyle = "#2563eb";
    ctx.fill();


    // ========================================================
    // 범례
    // ========================================================

    const legend = [
        {
            name: "실제 가격",
            color: "#2563eb"
        },
        {
            name: "단기 3시간",
            color: "#f59e0b"
        },
        {
            name: "중기 3일",
            color: "#16a34a"
        },
        {
            name: "장기 30일",
            color: "#9333ea"
        }
    ];

    let legendX = padding.left;

    const legendY = 18;

    ctx.textAlign = "left";
    ctx.textBaseline = "middle";

    legend.forEach(item => {
        ctx.beginPath();

        ctx.moveTo(legendX, legendY);
        ctx.lineTo(legendX + 18, legendY);

        ctx.strokeStyle = item.color;
        ctx.lineWidth = 3;
        ctx.stroke();

        ctx.fillStyle = "#475467";

        ctx.fillText(
            item.name,
            legendX + 24,
            legendY
        );

        legendX +=
            24 +
            ctx.measureText(item.name).width +
            22;
    });


    // ========================================================
    // 정보
    // ========================================================

    const shortCount =
        predictionSeries.short.length;

    const mediumCount =
        predictionSeries.medium.length;

    const longCount =
        predictionSeries.long.length;

    if (info) {
        info.textContent =
            `실제 ${actualSeries.length.toLocaleString("ko-KR")}개 · ` +
            `단기 예측 ${shortCount.toLocaleString("ko-KR")}개 · ` +
            `중기 예측 ${mediumCount.toLocaleString("ko-KR")}개 · ` +
            `장기 예측 ${longCount.toLocaleString("ko-KR")}개 · ` +
            `최근 ${latest.price.toLocaleString("ko-KR")}원`;
    }
}


// ============================================================
// 반응형
// ============================================================

let goldChartResizeTimer = null;

window.addEventListener("resize", () => {
    clearTimeout(goldChartResizeTimer);

    goldChartResizeTimer = setTimeout(() => {
        if (goldChartData.length) {
            drawAceGoldChart({
                series: {
                    ACE_KRX_GOLD: goldChartData
                },
                prediction_series: goldPredictionData
            });
        }
    }, 150);
});


'''

new_content = content[:start] + new_chart_js + content[end:]

HTML.write_text(new_content, encoding="utf-8")

# ------------------------------------------------------------
# JS 중복 검사
# ------------------------------------------------------------
final_text = HTML.read_text(encoding="utf-8")

checks = {
    "getPredictionSeries": len(re.findall(r"function\s+getPredictionSeries\s*\(", final_text)),
    "drawAceGoldChart": len(re.findall(r"function\s+drawAceGoldChart\s*\(", final_text)),
    "drawPredictionLine": len(re.findall(r"function\s+drawPredictionLine\s*\(", final_text)),
    "goldChartData": len(re.findall(r"\b(?:let|const|var)\s+goldChartData\s*=", final_text)),
    "goldPredictionData": len(re.findall(r"\b(?:let|const|var)\s+goldPredictionData\s*=", final_text)),
}

print()
print("==========================================")
print("그래프 JavaScript 교체 완료")
print("==========================================")

for key, count in checks.items():
    print(f"{key}: {count}개")

if checks["getPredictionSeries"] != 1:
    print("[WARNING] getPredictionSeries 중복 가능성이 있습니다.")

if checks["drawAceGoldChart"] != 1:
    print("[WARNING] drawAceGoldChart 중복 가능성이 있습니다.")

if checks["drawPredictionLine"] != 1:
    print("[WARNING] drawPredictionLine 중복 가능성이 있습니다.")

if checks["goldChartData"] > 1:
    print("[WARNING] goldChartData 선언이 중복되었습니다.")

if checks["goldPredictionData"] > 1:
    print("[WARNING] goldPredictionData 선언이 중복되었습니다.")

# ------------------------------------------------------------
# HTML에 필요한 전역 변수가 있는지 확인
# ------------------------------------------------------------
if not re.search(r"\b(?:let|const|var)\s+goldChartData\s*=", final_text):
    print("[ERROR] goldChartData 선언이 없습니다.")
    sys.exit(1)

if not re.search(r"\b(?:let|const|var)\s+goldPredictionData\s*=", final_text):
    print("[ERROR] goldPredictionData 선언이 없습니다.")
    print("기존 patch_dashboard_chart.py에서 선언을 추가해야 합니다.")
    sys.exit(1)

print()
print("[OK] 그래프 영역 Python 패치 완료")
print()
print("다음 확인:")
print("  grep -n 'function getPredictionSeries' templates/dashboard.html")
print("  grep -n 'function drawAceGoldChart' templates/dashboard.html")
print("  grep -n 'goldChartData' templates/dashboard.html")
print("  grep -n 'goldPredictionData' templates/dashboard.html")
print()
print("백업:")
print(f"  {BACKUP}")
