from pathlib import Path
import shutil
import re

HTML = Path("templates/dashboard.html")
BACKUP = Path("templates/dashboard.html.before_chart_zoom")

content = HTML.read_text(encoding="utf-8")

if not BACKUP.exists():
    shutil.copy2(HTML, BACKUP)
    print(f"[OK] 백업 생성 -> {BACKUP}")
else:
    print(f"[INFO] 기존 백업 사용 -> {BACKUP}")


# ============================================================
# 1. 기존 drawAceGoldChart 시작 부분에 줌 상태 추가
# ============================================================

zoom_state = r'''
// ============================================================
// 차트 줌 상태
//
// drag 시작 X / 현재 X를 저장하고
// 선택 영역을 시간 범위로 변환한다.
// ============================================================

let goldChartZoom = {
    active: false,
    startX: null,
    currentX: null,
    minTime: null,
    maxTime: null
};

let goldChartMouseDown = false;


// 화면 좌표를 Canvas 내부 좌표로 변환
function getGoldChartMouseX(event, canvas) {
    const rect = canvas.getBoundingClientRect();

    return event.clientX - rect.left;
}


// 선택 영역 그리기
function drawGoldChartSelection(canvas) {
    if (!goldChartMouseDown) {
        return;
    }

    if (
        goldChartZoom.startX == null ||
        goldChartZoom.currentX == null
    ) {
        return;
    }

    const ctx = canvas.getContext("2d");

    if (!ctx) {
        return;
    }

    const left = Math.min(
        goldChartZoom.startX,
        goldChartZoom.currentX
    );

    const right = Math.max(
        goldChartZoom.startX,
        goldChartZoom.currentX
    );

    if (right - left < 2) {
        return;
    }

    ctx.save();

    // 선택 영역
    ctx.fillStyle = "rgba(37, 99, 235, 0.12)";
    ctx.fillRect(
        left,
        0,
        right - left,
        canvas.clientHeight
    );

    // 선택 영역 테두리
    ctx.strokeStyle = "rgba(37, 99, 235, 0.65)";
    ctx.lineWidth = 1;

    ctx.beginPath();

    ctx.moveTo(left, 0);
    ctx.lineTo(left, canvas.clientHeight);

    ctx.moveTo(right, 0);
    ctx.lineTo(right, canvas.clientHeight);

    ctx.stroke();

    ctx.restore();
}


// ============================================================
// 실제 차트의 X축 시간 범위에 맞춰 줌
// ============================================================

function applyGoldChartZoom(canvas) {
    if (
        goldChartZoom.startX == null ||
        goldChartZoom.currentX == null
    ) {
        return;
    }

    const left = Math.min(
        goldChartZoom.startX,
        goldChartZoom.currentX
    );

    const right = Math.max(
        goldChartZoom.startX,
        goldChartZoom.currentX
    );

    const width = canvas.clientWidth;

    if (width <= 0) {
        return;
    }

    // 너무 작은 영역은 줌하지 않는다.
    if (right - left < 20) {
        return;
    }

    const minTime = goldChartZoom.minTime;
    const maxTime = goldChartZoom.maxTime;

    if (
        !Number.isFinite(minTime) ||
        !Number.isFinite(maxTime) ||
        maxTime <= minTime
    ) {
        return;
    }

    const startRatio =
        Math.max(0, Math.min(1, left / width));

    const endRatio =
        Math.max(0, Math.min(1, right / width));

    const selectedMinTime =
        minTime +
        startRatio *
        (maxTime - minTime);

    const selectedMaxTime =
        minTime +
        endRatio *
        (maxTime - minTime);

    if (
        !Number.isFinite(selectedMinTime) ||
        !Number.isFinite(selectedMaxTime) ||
        selectedMaxTime <= selectedMinTime
    ) {
        return;
    }

    goldChartZoom.active = true;
    goldChartZoom.minTime = selectedMinTime;
    goldChartZoom.maxTime = selectedMaxTime;

    goldChartMouseDown = false;

    drawAceGoldChart({
        series: {
            ACE_KRX_GOLD: goldChartData
        },
        prediction_series: goldPredictionData
    });
}


// ============================================================
// 줌 초기화
// ============================================================

function resetGoldChartZoom() {
    goldChartZoom.active = false;
    goldChartZoom.startX = null;
    goldChartZoom.currentX = null;
    goldChartZoom.minTime = null;
    goldChartZoom.maxTime = null;

    if (goldChartData.length) {
        drawAceGoldChart({
            series: {
                ACE_KRX_GOLD: goldChartData
            },
            prediction_series: goldPredictionData
        });
    }
}


// ============================================================
// Canvas 마우스 이벤트
// ============================================================

function setupGoldChartZoom(canvas) {
    if (!canvas) {
        return;
    }

    if (canvas.dataset.zoomReady === "true") {
        return;
    }

    canvas.dataset.zoomReady = "true";

    canvas.style.cursor = "crosshair";


    canvas.addEventListener("mousedown", event => {
        if (event.button !== 0) {
            return;
        }

        const x =
            getGoldChartMouseX(event, canvas);

        goldChartMouseDown = true;

        goldChartZoom.startX = x;
        goldChartZoom.currentX = x;

        // 현재 표시 중인 X축 범위를 저장
        const allPoints = [];

        goldChartData.forEach(item => {
            allPoints.push(item);
        });

        ["short", "medium", "long"].forEach(horizon => {
            (goldChartPredictionData?.[horizon] || []).forEach(item => {
                allPoints.push(item);
            });
        });

        // 실제 변수 사용
        if (goldPredictionData) {
            ["short", "medium", "long"].forEach(horizon => {
                (goldPredictionData[horizon] || []).forEach(item => {
                    allPoints.push(item);
                });
            });
        }

        const timestamps = allPoints
            .map(item =>
                new Date(item.timestamp).getTime()
            )
            .filter(value =>
                Number.isFinite(value)
            );

        if (!timestamps.length) {
            return;
        }

        let minTime =
            goldChartZoom.active
                ? goldChartZoom.minTime
                : Math.min(...timestamps);

        let maxTime =
            goldChartZoom.active
                ? goldChartZoom.maxTime
                : Math.max(...timestamps);

        if (minTime === maxTime) {
            minTime -= 3600000;
            maxTime += 3600000;
        }

        goldChartZoom._displayMinTime = minTime;
        goldChartZoom._displayMaxTime = maxTime;

        event.preventDefault();
    });


    canvas.addEventListener("mousemove", event => {
        if (!goldChartMouseDown) {
            return;
        }

        goldChartZoom.currentX =
            getGoldChartMouseX(event, canvas);

        // 현재 차트를 다시 그리면 선택 영역이 사라지므로
        // 기존 화면 위에 선택 영역만 표시한다.
        drawGoldChartSelection(canvas);

        event.preventDefault();
    });


    window.addEventListener("mouseup", event => {
        if (!goldChartMouseDown) {
            return;
        }

        const rect =
            canvas.getBoundingClientRect();

        const x =
            event.clientX - rect.left;

        goldChartZoom.currentX = x;

        goldChartZoom.minTime =
            goldChartZoom._displayMinTime;

        goldChartZoom.maxTime =
            goldChartZoom._displayMaxTime;

        applyGoldChartZoom(canvas);
    });


    // 더블클릭 = 전체 보기
    canvas.addEventListener("dblclick", event => {
        event.preventDefault();

        resetGoldChartZoom();
    });
}
'''


# 중복 방지
if "let goldChartZoom =" not in content:
    marker = "function drawAceGoldChart(data) {"

    if marker not in content:
        print("[ERROR] drawAceGoldChart를 찾지 못했습니다.")
        raise SystemExit(1)

    content = content.replace(
        marker,
        zoom_state + "\n\n" + marker,
        1
    )

    print("[OK] 차트 줌 기능 코드 추가")
else:
    print("[INFO] 차트 줌 기능이 이미 존재합니다.")


# ============================================================
# 2. drawAceGoldChart에서 시간 범위 계산 부분을 줌 상태와 연결
# ============================================================

old = r'''    let minTime = Math.min(...timestamps);
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
'''

new = r'''    let minTime = Math.min(...timestamps);
    let maxTime = Math.max(...timestamps);

    if (minTime === maxTime) {
        minTime -= 3600000;
        maxTime += 3600000;
    }

    // --------------------------------------------------------
    // 줌 상태가 있으면 선택된 시간 범위 사용
    // --------------------------------------------------------

    if (
        goldChartZoom &&
        goldChartZoom.active &&
        Number.isFinite(goldChartZoom.minTime) &&
        Number.isFinite(goldChartZoom.maxTime) &&
        goldChartZoom.maxTime > goldChartZoom.minTime
    ) {
        minTime = goldChartZoom.minTime;
        maxTime = goldChartZoom.maxTime;
    } else {
        const timeRange = maxTime - minTime;

        // 과거 쪽 여유
        minTime -= timeRange * 0.02;

        // 미래 예측을 볼 수 있도록 오른쪽 여유
        maxTime += timeRange * 0.05;
    }
'''

if old in content:
    content = content.replace(old, new, 1)
    print("[OK] X축 줌 범위 연결")
else:
    print("[WARNING] 기존 시간 범위 코드를 찾지 못했습니다.")


# ============================================================
# 3. drawAceGoldChart 안에서 이벤트 연결
# ============================================================

setup_code = r'''
    // 마우스 드래그 줌 활성화
    setupGoldChartZoom(canvas);
'''

# 마지막 정보 출력 부분 직전에 넣는다.
marker = "    // ========================================================\n    // 실제 최신 가격"

if setup_code.strip() not in content:
    if marker in content:
        content = content.replace(
            marker,
            setup_code + "\n\n" + marker,
            1
        )
        print("[OK] Canvas 줌 이벤트 연결")
    else:
        print("[WARNING] 최신 가격 렌더링 위치를 찾지 못했습니다.")


# ============================================================
# 4. resize 시 줌 상태 유지
# ============================================================

# 기존 resize에서 drawAceGoldChart가 실행되므로
# goldChartZoom.active 상태만 유지하면 된다.


# ============================================================
# 5. 오타 방지
# ============================================================

content = content.replace(
    "goldChartPredictionData?.",
    "goldPredictionData?."
)


HTML.write_text(content, encoding="utf-8")


# ============================================================
# 검사
# ============================================================

print()
print("==========================================")
print("차트 줌 패치 검사")
print("==========================================")

checks = [
    "let goldChartZoom",
    "function setupGoldChartZoom",
    "function applyGoldChartZoom",
    "function resetGoldChartZoom",
    "mousedown",
    "mousemove",
    "dblclick",
    "goldChartZoom.active"
]

failed = False

for check in checks:
    count = content.count(check)

    if count:
        print(f"[OK] {check}: {count}개")
    else:
        print(f"[ERROR] {check}: 없음")
        failed = True


print()

if failed:
    print("[ERROR] 줌 패치 검증 실패")
    raise SystemExit(1)

print("[SUCCESS] 차트 마우스 드래그 줌 기능 패치 완료")
print()
print("사용법:")
print("  1. 차트에서 마우스 왼쪽 버튼을 누릅니다.")
print("  2. 보고 싶은 구간까지 드래그합니다.")
print("  3. 마우스 버튼을 놓으면 해당 구간이 확대됩니다.")
print("  4. 더블클릭하면 전체 범위로 돌아옵니다.")
print()
print(f"백업: {BACKUP}")
