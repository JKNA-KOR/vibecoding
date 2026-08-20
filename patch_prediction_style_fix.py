from pathlib import Path
import re
import shutil
import sys


BASE_DIR = Path(__file__).resolve().parent
HTML_FILE = BASE_DIR / "templates" / "dashboard.html"
BACKUP_FILE = BASE_DIR / "templates" / "dashboard.html.before_prediction_style_fix"


if not HTML_FILE.exists():
    print(f"[ERROR] 파일을 찾을 수 없습니다: {HTML_FILE}")
    sys.exit(1)


# ------------------------------------------------------------
# 백업
# ------------------------------------------------------------
if not BACKUP_FILE.exists():
    shutil.copy2(HTML_FILE, BACKUP_FILE)
    print(f"[OK] 백업 생성 -> {BACKUP_FILE}")
else:
    print(f"[INFO] 기존 백업 사용 -> {BACKUP_FILE}")


content = HTML_FILE.read_text(encoding="utf-8")


# ------------------------------------------------------------
# 1. drawPredictionPoints 함수가 없으면 추가
# ------------------------------------------------------------
points_function = r'''
// ------------------------------------------------------------
// 예측값 표시 점
// ------------------------------------------------------------
function drawPredictionPoints(
    ctx,
    points,
    x,
    y,
    color
) {
    if (!Array.isArray(points) || !points.length) {
        return;
    }

    points.forEach(item => {
        const date = new Date(item.timestamp);

        if (Number.isNaN(date.getTime())) {
            return;
        }

        const xx = x(date);
        const yy = y(item.price);

        // 외곽 원
        ctx.beginPath();
        ctx.arc(xx, yy, 4.5, 0, Math.PI * 2);

        ctx.fillStyle = "#ffffff";
        ctx.fill();

        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.stroke();

        // 내부 점
        ctx.beginPath();
        ctx.arc(xx, yy, 2.5, 0, Math.PI * 2);

        ctx.fillStyle = color;
        ctx.fill();
    });
}
'''


if "function drawPredictionPoints(" not in content:
    marker = "// ------------------------------------------------------------\n// ACE KRX금현물 그래프"

    if marker not in content:
        print("[ERROR] drawAceGoldChart 삽입 위치를 찾을 수 없습니다.")
        sys.exit(1)

    content = content.replace(
        marker,
        points_function.strip() + "\n\n\n" + marker,
        1
    )

    print("[OK] drawPredictionPoints 함수 추가")
else:
    print("[INFO] drawPredictionPoints 함수가 이미 존재합니다.")


# ------------------------------------------------------------
# 2. drawPredictionLine 함수 수정
#
# 마지막 인자:
#   dashed = false
# ------------------------------------------------------------
pattern = re.compile(
    r"function drawPredictionLine\(\s*"
    r"ctx,\s*"
    r"points,\s*"
    r"x,\s*"
    r"y,\s*"
    r"padding,\s*"
    r"chartWidth,\s*"
    r"chartHeight,\s*"
    r"color,\s*"
    r"lineWidth"
    r"(?:,\s*dashed)?\s*"
    r"\)\s*\{.*?"
    r"\n\}",
    re.DOTALL
)


new_draw_prediction_line = r'''function drawPredictionLine(
    ctx,
    points,
    x,
    y,
    padding,
    chartWidth,
    chartHeight,
    color,
    lineWidth,
    dashed = false
) {
    if (!Array.isArray(points) || !points.length) {
        return;
    }

    ctx.beginPath();

    let started = false;

    points.forEach(item => {
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

    // 실제 시세 = 실선
    // 예측 = 점선
    if (dashed) {
        ctx.setLineDash([6, 6]);
    } else {
        ctx.setLineDash([]);
    }

    ctx.stroke();

    // 다음 그래프를 위해 반드시 초기화
    ctx.setLineDash([]);
}'''


match = pattern.search(content)

if match:
    content = (
        content[:match.start()]
        + new_draw_prediction_line
        + content[match.end():]
    )
    print("[OK] drawPredictionLine 수정 완료")
else:
    print("[WARNING] drawPredictionLine 함수 전체 교체 위치를 찾지 못했습니다.")


# ------------------------------------------------------------
# 3. 실제 시세선
# ------------------------------------------------------------
actual_call_pattern = re.compile(
    r"(drawPredictionLine\(\s*"
    r"ctx,\s*"
    r"actualSeries,\s*"
    r"x,\s*"
    r"y,\s*"
    r"padding,\s*"
    r"chartWidth,\s*"
    r"chartHeight,\s*"
    r'"#2563eb",\s*'
    r")2\.5\s*\)"
)


content, actual_count = actual_call_pattern.subn(
    r'\g<1>4\n    )',
    content,
    count=1
)

if actual_count:
    print("[OK] 실제 시세선 두께 = 4px")


# ------------------------------------------------------------
# 4. 예측선에 dashed=true 적용
# ------------------------------------------------------------
prediction_colors = [
    "#f59e0b",
    "#16a34a",
    "#9333ea",
]

for color in prediction_colors:
    pattern = re.compile(
        r'(drawPredictionLine\(\s*'
        r'ctx,\s*'
        r'predictionSeries\.(?:short|medium|long),\s*'
        r'x,\s*'
        r'y,\s*'
        r'padding,\s*'
        r'chartWidth,\s*'
        r'chartHeight,\s*'
        r'"' + re.escape(color) + r'",\s*'
        r'2\.5?)\s*'
        r'\)'
    )

    content, count = pattern.subn(
        r'\g<1>,\n        true\n    )',
        content,
        count=1
    )

    if count:
        print(f"[OK] {color} 예측선 점선 적용")


# ------------------------------------------------------------
# 5. 예측점 추가
#
# 예측선 바로 다음에 표시
# ------------------------------------------------------------
prediction_point_blocks = [
    (
        "predictionSeries.short",
        "#f59e0b",
        "단기"
    ),
    (
        "predictionSeries.medium",
        "#16a34a",
        "중기"
    ),
    (
        "predictionSeries.long",
        "#9333ea",
        "장기"
    ),
]


for series_name, color, label in prediction_point_blocks:

    call = f'''    drawPredictionPoints(
        ctx,
        {series_name},
        x,
        y,
        "{color}"
    );'''

    # 같은 호출이 없을 때만 추가
    if call not in content:

        # 해당 drawPredictionLine 호출의 닫는 위치를 찾아
        # 바로 다음에 점을 추가하기가 복잡하므로
        # 색상별 마지막 occurrence 뒤에 추가
        color_marker = f'"{color}",'

        pos = content.find(color_marker)

        if pos != -1:
            # 해당 색상이 포함된 drawPredictionLine 블록의 끝 찾기
            end = content.find("\n    );", pos)

            if end != -1:
                end += len("\n    );")

                content = (
                    content[:end]
                    + "\n\n\n"
                    + call
                    + content[end:]
                )

                print(f"[OK] {label} 예측점 추가")


# ------------------------------------------------------------
# 6. 실제 최신 가격 점을 더 강조
# ------------------------------------------------------------
latest_point_pattern = re.compile(
    r"ctx\.arc\(\s*"
    r"latestX,\s*"
    r"latestY,\s*"
    r"5,\s*"
    r"0,\s*"
    r"Math\.PI\s*\*\s*2\s*"
    r"\);"
)

content, latest_count = latest_point_pattern.subn(
    """ctx.arc(
        latestX,
        latestY,
        7,
        0,
        Math.PI * 2
    );""",
    content,
    count=1
)

if latest_count:
    print("[OK] 실제 최신 가격 점 = 7px")


# ------------------------------------------------------------
# 7. setLineDash 안전 초기화
# ------------------------------------------------------------
if "ctx.setLineDash([]);" not in content:
    print("[WARNING] setLineDash 초기화 코드가 없습니다.")


# ------------------------------------------------------------
# 8. 저장
# ------------------------------------------------------------
HTML_FILE.write_text(content, encoding="utf-8")


# ------------------------------------------------------------
# 9. 기본 검증
# ------------------------------------------------------------
checks = {
    "drawPredictionPoints": len(
        re.findall(r"function drawPredictionPoints\s*\(", content)
    ),
    "drawPredictionLine": len(
        re.findall(r"function drawPredictionLine\s*\(", content)
    ),
    "drawAceGoldChart": len(
        re.findall(r"function drawAceGoldChart\s*\(", content)
    ),
    "goldChartData": len(
        re.findall(r"\bgoldChartData\b", content)
    ),
    "goldPredictionData": len(
        re.findall(r"\bgoldPredictionData\b", content)
    ),
}


print()
print("=" * 55)
print("그래프 스타일 패치 완료")
print("=" * 55)

for name, count in checks.items():
    print(f"{name}: {count}개")

print()
print("적용 내용:")
print("  실제 가격 : 굵은 실선 4px")
print("  단기 3시간: 주황색 점선 + 예측점")
print("  중기 3일  : 녹색 점선 + 예측점")
print("  장기 30일 : 보라색 점선 + 예측점")
print("  최신 실제가격 점: 7px")
print()
print(f"백업: {BACKUP_FILE}")
print(f"수정: {HTML_FILE}")