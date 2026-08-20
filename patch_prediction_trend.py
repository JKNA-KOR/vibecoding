from pathlib import Path
import py_compile
import shutil
import sys


PATCH_FILE = Path("patch_dashboard_chart.py")
BACKUP_FILE = Path("patch_dashboard_chart.py.before_prediction_trend")


NEW_CHART_JS = r'''
// ------------------------------------------------------------
// ACE KRX금현물 + 과거/현재/미래 예측 추세 그래프
// ------------------------------------------------------------
let goldChartData = [];
let goldPredictionData = {
    short: [],
    medium: [],
    long: []
};

function getAceGoldSeries(data) {
    const series = data?.series?.ACE_KRX_GOLD;

    if (!Array.isArray(series)) {
        return [];
    }

    return series
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
        .sort((a, b) =>
            new Date(a.timestamp) - new Date(b.timestamp)
        );
}


// ------------------------------------------------------------
// DB에 저장된 과거 예측 + 현재 예측
//
// 중요:
// predicted_at     = 예측을 만든 시간
// target_timestamp = 실제로 예측한 미래 시점
//
// 그래프에서는 target_timestamp를 x축 위치로 사용한다.
// ------------------------------------------------------------
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
                predicted_at: item.predicted_at || item.timestamp,
                price: Number(item.price),
                recommendation: item.recommendation || "",
                confidence: item.confidence || "",
                training_mode: item.training_mode || ""
            }))
            .sort((a, b) =>
                new Date(a.timestamp) - new Date(b.timestamp)
            );
    }

    return result;
}


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
        return timestamp;
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
// 모든 가격을 하나의 시간축으로 합쳐서 Y축 범위를 계산
// ------------------------------------------------------------
function getAllChartPrices(actual, predictions) {
    const prices = [];

    actual.forEach(item => {
        prices.push(item.price);
    });

    ["short", "medium", "long"].forEach(horizon => {
        predictions[horizon].forEach(item => {
            prices.push(item.price);
        });
    });

    return prices.filter(price =>
        Number.isFinite(price)
    );
}


// ------------------------------------------------------------
// 선 그리기
//
// null 구간을 허용하여 과거 예측과 미래 예측이
// 실제 가격선과 자연스럽게 겹치도록 한다.
// ------------------------------------------------------------
function drawPredictionLine(
    ctx,
    points,
    x,
    y,
    padding,
    chartWidth,
    chartHeight,
    color,
    lineWidth
) {
    if (!points.length) {
        return;
    }

    ctx.beginPath();

    let started = false;

    points.forEach((item, index) => {
        const date = new Date(item.timestamp);

        if (Number.isNaN(date.getTime())) {
            return;
        }

        const xx = x(date);
        const yy = y(item.price);

        if (!started) {
            ctx.moveTo(xx, yy);
            started = true;
        } else {
            ctx.lineTo(xx, yy);
        }
    });

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
// ACE KRX금현물 그래프
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
            info.textContent = "데이터 없음";
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

    const dpr = window.devicePixelRatio || 1;

    canvas.width = width * dpr;
    canvas.height = height * dpr;

    canvas.style.width = width + "px";
    canvas.style.height = height + "px";

    const ctx = canvas.getContext("2d");

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const padding = {
        top: 35,
        right: 30,
        bottom: 48,
        left: 72
    };

    const chartWidth =
        width - padding.left - padding.right;

    const chartHeight =
        height - padding.top - padding.bottom;

    if (chartWidth <= 0 || chartHeight <= 0) {
        return;
    }


    // --------------------------------------------------------
    // 전체 시간 범위
    //
    // 실제 가격 + 과거 예측 + 미래 예측
    // --------------------------------------------------------
    const allPoints = [];

    actualSeries.forEach(item => {
        allPoints.push({
            timestamp: item.timestamp,
            price: item.price
        });
    });

    ["short", "medium", "long"].forEach(horizon => {
        predictionSeries[horizon].forEach(item => {
            allPoints.push({
                timestamp: item.timestamp,
                price: item.price
            });
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

    // 미래 예측이 없으면 실제 데이터 기준
    if (minTime === maxTime) {
        minTime -= 3600000;
        maxTime += 3600000;
    }

    // 좌우 시간 여유
    const timeRange = maxTime - minTime;

    minTime -= timeRange * 0.02;
    maxTime += timeRange * 0.08;


    // --------------------------------------------------------
    // Y축 범위
    // --------------------------------------------------------
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


    // --------------------------------------------------------
    // 좌표 변환
    // --------------------------------------------------------
    const x = timestamp => {
        const time = new Date(timestamp).getTime();

        return padding.left +
            ((time - minTime) / (maxTime - minTime)) *
            chartWidth;
    };

    const y = price =>
        padding.top +
        ((maxPrice - price) /
            (maxPrice - minPrice)) *
        chartHeight;


    ctx.clearRect(0, 0, width, height);


    // --------------------------------------------------------
    // Grid
    // --------------------------------------------------------
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


    // --------------------------------------------------------
    // X축
    // --------------------------------------------------------
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
            formatChartTime(timestamp),
            xx,
            height - padding.bottom + 12
        );
    }


    // --------------------------------------------------------
    // 실제 가격선
    // --------------------------------------------------------
    drawPredictionLine(
        ctx,
        actualSeries,
        x,
        y,
        padding,
        chartWidth,
        chartHeight,
        "#2563eb",
        2.5
    );


    // --------------------------------------------------------
    // 예측선
    //
    // short  = 주황색
    // medium = 초록색
    // long   = 보라색
    // --------------------------------------------------------
    drawPredictionLine(
        ctx,
        predictionSeries.short,
        x,
        y,
        padding,
        chartWidth,
        chartHeight,
        "#f59e0b",
        2
    );

    drawPredictionLine(
        ctx,
        predictionSeries.medium,
        x,
        y,
        padding,
        chartWidth,
        chartHeight,
        "#16a34a",
        2
    );

    drawPredictionLine(
        ctx,
        predictionSeries.long,
        x,
        y,
        padding,
        chartWidth,
        chartHeight,
        "#9333ea",
        2
    );


    // --------------------------------------------------------
    // 실제 가격 최신점
    // --------------------------------------------------------
    const latest = actualSeries[actualSeries.length - 1];

    const latestX = x(latest.timestamp);
    const latestY = y(latest.price);

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


    // --------------------------------------------------------
    // 범례
    // --------------------------------------------------------
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
    const legendY = 12;

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


    // --------------------------------------------------------
    // 정보
    // --------------------------------------------------------
    const shortCount = predictionSeries.short.length;
    const mediumCount = predictionSeries.medium.length;
    const longCount = predictionSeries.long.length;

    if (info) {
        info.textContent =
            `실제 ${actualSeries.length.toLocaleString("ko-KR")}개 · ` +
            `단기 예측 ${shortCount.toLocaleString("ko-KR")}개 · ` +
            `중기 예측 ${mediumCount.toLocaleString("ko-KR")}개 · ` +
            `장기 예측 ${longCount.toLocaleString("ko-KR")}개 · ` +
            `최근 ${latest.price.toLocaleString("ko-KR")}원`;
    }
}


// ------------------------------------------------------------
// 반응형
// ------------------------------------------------------------
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


def main():
    if not PATCH_FILE.exists():
        print(f"[ERROR] 파일을 찾을 수 없습니다: {PATCH_FILE}")
        sys.exit(1)

    content = PATCH_FILE.read_text(encoding="utf-8")

    start_marker = "chart_js = r'''"

    start = content.find(start_marker)

    if start == -1:
        print("[ERROR] chart_js = r''' 위치를 찾지 못했습니다.")
        sys.exit(1)

    js_start = start + len(start_marker)

    # chart_js 문자열의 끝을 찾는다.
    end = content.find("'''", js_start)

    if end == -1:
        print("[ERROR] chart_js 종료 ''' 를 찾지 못했습니다.")
        sys.exit(1)

    if not BACKUP_FILE.exists():
        shutil.copy2(PATCH_FILE, BACKUP_FILE)
        print(f"[OK] 백업 생성 -> {BACKUP_FILE}")
    else:
        print(f"[INFO] 기존 백업 사용 -> {BACKUP_FILE}")

    new_content = (
        content[:start]
        + "chart_js = r'''"
        + NEW_CHART_JS
        + "'''"
        + content[end + 3:]
    )

    PATCH_FILE.write_text(new_content, encoding="utf-8")

    print("[OK] 4개 선 그래프 JavaScript 교체 완료")
    print()
    print("구성:")
    print("  1. 실제 ACE KRX금현물")
    print("  2. 단기 3시간 예측")
    print("  3. 중기 3일 예측")
    print("  4. 장기 30일 예측")
    print()
    print("중요:")
    print("  과거 예측은 predicted_at이 아니라 target_timestamp에 표시합니다.")
    print("  따라서 과거 예측 추세와 실제 가격 추세를 동일한 시간축에서 비교합니다.")
    print()

    # 패치 스크립트 자체 문법 검사
    try:
        py_compile.compile(
            str(PATCH_FILE),
            doraise=True
        )
        print("[OK] patch_dashboard_chart.py Python 문법 검사 통과")
    except Exception as exc:
        print(f"[ERROR] patch_dashboard_chart.py 문법 오류: {exc}")
        print()
        print(f"백업에서 복구하려면:")
        print(f"cp {BACKUP_FILE} {PATCH_FILE}")
        sys.exit(1)

    print()
    print("다음 실행:")
    print("  python3 patch_dashboard_chart.py")


if __name__ == "__main__":
    main()
