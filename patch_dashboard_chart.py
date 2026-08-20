from pathlib import Path
import shutil
import sys

path = Path("templates/dashboard.html")
backup = Path("templates/dashboard.html.bak")

if not path.exists():
    print(f"[ERROR] 파일이 없습니다: {path}")
    sys.exit(1)

original = path.read_text(encoding="utf-8")

# ------------------------------------------------------------
# 1. 백업
# ------------------------------------------------------------
shutil.copy2(path, backup)
print(f"[OK] 백업 생성: {backup}")

content = original

# ------------------------------------------------------------
# 2. HTML 오타 수정
# ------------------------------------------------------------
content = content.replace(
    '<div id="shortPrice"class="prediction-price">',
    '<div id="shortPrice" class="prediction-price">'
)

content = content.replace(
    '<divclass="label">',
    '<div class="label">'
)

# ------------------------------------------------------------
# 3. 그래프 CSS 추가
# ------------------------------------------------------------
chart_css = r'''
.chart-card{
    background:#fff;
    border:1px solid #e5e9f0;
    border-radius:14px;
    padding:18px;
    box-shadow:0 2px 8px rgba(16,24,40,.04);
}

.chart-header{
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:12px;
    margin-bottom:12px;
}

.chart-title{
    font-size:18px;
    font-weight:800;
}

.chart-info{
    color:#667085;
    font-size:13px;
}

.chart-container{
    position:relative;
    width:100%;
    height:360px;
}

#goldChart{
    width:100%;
    height:100%;
    display:block;
}

.chart-empty{
    position:absolute;
    inset:0;
    display:flex;
    align-items:center;
    justify-content:center;
    color:#667085;
    font-size:14px;
    pointer-events:none;
}

@media(max-width:650px){
    .chart-container{
        height:280px;
    }

    .chart-header{
        align-items:flex-start;
        flex-direction:column;
    }
}
'''

style_marker = '</style>'

if chart_css.strip() not in content:
    if style_marker not in content:
        print("[ERROR] </style> 태그를 찾을 수 없습니다.")
        sys.exit(1)

    content = content.replace(
        style_marker,
        chart_css + style_marker,
        1
    )
    print("[OK] 그래프 CSS 추가")

# ------------------------------------------------------------
# 4. 그래프 HTML 추가
# ------------------------------------------------------------
chart_html = r'''
<div class="section-title">ACE KRX금현물 시세 추세</div>
<div class="chart-card">
    <div class="chart-header">
        <div class="chart-title">ACE KRX금현물</div>
        <div id="goldChartInfo" class="chart-info">데이터를 불러오는 중...</div>
    </div>

    <div class="chart-container">
        <canvas id="goldChart"></canvas>
        <div id="goldChartEmpty" class="chart-empty" style="display:none;">
            시세 데이터가 없습니다.
        </div>
    </div>
</div>
'''

market_marker = '<div class="section-title">시장 데이터</div>'

if chart_html.strip() not in content:
    if market_marker not in content:
        print("[ERROR] 시장 데이터 영역을 찾을 수 없습니다.")
        sys.exit(1)

    content = content.replace(
        market_marker,
        chart_html + market_marker,
        1
    )
    print("[OK] 그래프 HTML 추가")

# ------------------------------------------------------------
# 5. 그래프 JavaScript 추가
# ------------------------------------------------------------
chart_js = r'''
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

# render(d) 내부에서 그래프를 그리도록 추가
render_marker = 'function render(d){'

if chart_js.strip() not in content:
    if render_marker not in content:
        print("[ERROR] render(d) 함수를 찾을 수 없습니다.")
        sys.exit(1)

    content = content.replace(
        render_marker,
        chart_js + "\n" + render_marker,
        1
    )
    print("[OK] 그래프 JavaScript 추가")

# render(d) 함수 내부에 호출 추가
render_call = ' drawAceGoldChart(d);'

if render_call.strip() not in content:
    status_marker = ' const status=document.getElementById("status");'

    if status_marker not in content:
        print("[ERROR] render 함수 삽입 위치를 찾을 수 없습니다.")
        sys.exit(1)

    content = content.replace(
        status_marker,
        render_call + "\n" + status_marker,
        1
    )

    print("[OK] 그래프 렌더링 호출 추가")

# ------------------------------------------------------------
# 6. 변경사항 확인
# ------------------------------------------------------------
if content == original:
    print("[WARNING] 변경사항이 없습니다.")
    sys.exit(0)

path.write_text(content, encoding="utf-8")

print()
print("=" * 60)
print("[SUCCESS] dashboard.html 패치 완료")
print("=" * 60)
print(f"원본 백업 : {backup}")
print(f"수정 파일 : {path}")
print()
print("다음 명령으로 변경사항을 확인하세요:")
print("  git diff -- templates/dashboard.html")
print()
print("그래프 관련 코드 확인:")
print('  grep -n "goldChart\\|ACE KRX금현물 시세 추세" templates/dashboard.html')
