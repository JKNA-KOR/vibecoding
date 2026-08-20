from pathlib import Path
import shutil
import re
import sys


BASE_DIR = Path(__file__).resolve().parent
HTML_FILE = BASE_DIR / "templates" / "dashboard.html"
BACKUP_FILE = BASE_DIR / "templates" / "dashboard.html.before_chart_style"


if not HTML_FILE.exists():
    print(f"[ERROR] 파일을 찾을 수 없습니다: {HTML_FILE}")
    sys.exit(1)


# ------------------------------------------------------------
# 백업
# ------------------------------------------------------------
if not BACKUP_FILE.exists():
    shutil.copy2(HTML_FILE, BACKUP_FILE)
    print(f"[OK] 백업 생성: {BACKUP_FILE}")
else:
    print(f"[INFO] 기존 백업 사용: {BACKUP_FILE}")


content = HTML_FILE.read_text(encoding="utf-8")


# ------------------------------------------------------------
# 1. drawPredictionLine 함수 교체
# ------------------------------------------------------------
start_marker = "function drawPredictionLine("
start = content.find(start_marker)

if start == -1:
    print("[ERROR] drawPredictionLine 함수를 찾을 수 없습니다.")
    sys.exit(1)


# 다음 함수인 drawAceGoldChart 직전까지
end_marker = "function drawAceGoldChart("
end = content.find(end_marker, start)

if end == -1:
    print("[ERROR] drawAceGoldChart 함수를 찾을 수 없습니다.")
    sys.exit(1)


new_draw_prediction_line = r'''function drawPredictionLine(
    ctx,
    points,
    x,
    y,
    padding,
    chartWidth,
    chartHeight,
    color,
    lineWidth = 2,
    dashed = true,
    pointRadius = 2.5
) {
    if (!points || !points.length) {
        return;
    }

    // --------------------------------------------------------
    // 예측선
    //
    // dashed=true
    //   -> 예측값은 점선
    //
    // dashed=false
    //   -> 실제 가격은 실선
    // --------------------------------------------------------
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

    // 실제 가격 = 실선
    // 예측 = 점선
    if (dashed) {
        ctx.setLineDash([7, 5]);
    } else {
        ctx.setLineDash([]);
    }

    ctx.lineJoin = "round";
    ctx.lineCap = "round";

    ctx.stroke();

    // --------------------------------------------------------
    // 예측값 포인트
    // --------------------------------------------------------
    if (dashed) {
        ctx.setLineDash([]);

        points.forEach(item => {
            const date = new Date(item.timestamp);

            if (Number.isNaN(date.getTime())) {
                return;
            }

            const xx = x(date);
            const yy = y(item.price);

            ctx.beginPath();
            ctx.arc(
                xx,
                yy,
                pointRadius,
                0,
                Math.PI * 2
            );

            ctx.fillStyle = color;
            ctx.fill();
        });
    }

    // 다음 선에 영향을 주지 않도록 초기화
    ctx.setLineDash([]);
}


'''


content = (
    content[:start]
    + new_draw_prediction_line
    + content[end:]
)

print("[OK] drawPredictionLine 교체")


# ------------------------------------------------------------
# 2. 실제 가격선 호출 변경
# ------------------------------------------------------------
actual_pattern = re.compile(
    r'''drawPredictionLine\(
\s*ctx,
\s*actualSeries,
\s*x,
\s*y,
\s*padding,
\s*chartWidth,
\s*chartHeight,
\s*"#2563eb",
\s*2\.5
\s*\);''',
    re.MULTILINE,
)

actual_replacement = '''drawPredictionLine(
        ctx,
        actualSeries,
        x,
        y,
        padding,
        chartWidth,
        chartHeight,
        "#2563eb",
        4,
        false,
        0
    );'''


content, actual_count = actual_pattern.subn(
    actual_replacement,
    content,
    count=1,
)

if actual_count:
    print("[OK] 실제 시세선 굵게 변경: 4px 실선")
else:
    print("[WARNING] 실제 시세선 호출을 찾지 못했습니다.")


# ------------------------------------------------------------
# 3. 단기 예측선
# ------------------------------------------------------------
short_pattern = re.compile(
    r'''drawPredictionLine\(
\s*ctx,
\s*predictionSeries\.short,
\s*x,
\s*y,
\s*padding,
\s*chartWidth,
\s*chartHeight,
\s*"#f59e0b",
\s*2
\s*\);''',
    re.MULTILINE,
)

short_replacement = '''drawPredictionLine(
        ctx,
        predictionSeries.short,
        x,
        y,
        padding,
        chartWidth,
        chartHeight,
        "#f59e0b",
        2,
        true,
        2.5
    );'''

content, short_count = short_pattern.subn(
    short_replacement,
    content,
    count=1,
)

if short_count:
    print("[OK] 단기 예측선: 주황색 점선")
else:
    print("[WARNING] 단기 예측선 호출을 찾지 못했습니다.")


# ------------------------------------------------------------
# 4. 중기 예측선
# ------------------------------------------------------------
medium_pattern = re.compile(
    r'''drawPredictionLine\(
\s*ctx,
\s*predictionSeries\.medium,
\s*x,
\s*y,
\s*padding,
\s*chartWidth,
\s*chartHeight,
\s*"#16a34a",
\s*2
\s*\);''',
    re.MULTILINE,
)

medium_replacement = '''drawPredictionLine(
        ctx,
        predictionSeries.medium,
        x,
        y,
        padding,
        chartWidth,
        chartHeight,
        "#16a34a",
        2,
        true,
        2.5
    );'''

content, medium_count = medium_pattern.subn(
    medium_replacement,
    content,
    count=1,
)

if medium_count:
    print("[OK] 중기 예측선: 초록색 점선")
else:
    print("[WARNING] 중기 예측선 호출을 찾지 못했습니다.")


# ------------------------------------------------------------
# 5. 장기 예측선
# ------------------------------------------------------------
long_pattern = re.compile(
    r'''drawPredictionLine\(
\s*ctx,
\s*predictionSeries\.long,
\s*x,
\s*y,
\s*padding,
\s*chartWidth,
\s*chartHeight,
\s*"#9333ea",
\s*2
\s*\);''',
    re.MULTILINE,
)

long_replacement = '''drawPredictionLine(
        ctx,
        predictionSeries.long,
        x,
        y,
        padding,
        chartWidth,
        chartHeight,
        "#9333ea",
        2,
        true,
        2.5
    );'''

content, long_count = long_pattern.subn(
    long_replacement,
    content,
    count=1,
)

if long_count:
    print("[OK] 장기 예측선: 보라색 점선")
else:
    print("[WARNING] 장기 예측선 호출을 찾지 못했습니다.")


# ------------------------------------------------------------
# 6. 최신 실제 가격 표시를 더 크게
# ------------------------------------------------------------
latest_pattern = re.compile(
    r'''ctx\.arc\(
\s*latestX,
\s*latestY,
\s*5,
\s*0,
\s*Math\.PI \* 2
\s*\);''',
    re.MULTILINE,
)

latest_replacement = '''ctx.arc(
        latestX,
        latestY,
        7,
        0,
        Math.PI * 2
    );'''

content, latest_count = latest_pattern.subn(
    latest_replacement,
    content,
    count=1,
)

if latest_count:
    print("[OK] 최신 실제 시세 점 확대: 7px")
else:
    print("[WARNING] 최신 가격 점을 찾지 못했습니다.")


# ------------------------------------------------------------
# 7. 최신 실제 가격 주변 강조 링 추가
# ------------------------------------------------------------
anchor = '''ctx.fillStyle = "#2563eb";
    ctx.fill();


    // --------------------------------------------------------
    // 범례
'''

replacement = '''ctx.fillStyle = "#2563eb";
    ctx.fill();

    // 최신 실제 가격 강조 링
    ctx.beginPath();

    ctx.arc(
        latestX,
        latestY,
        11,
        0,
        Math.PI * 2
    );

    ctx.strokeStyle = "rgba(37, 99, 235, 0.22)";
    ctx.lineWidth = 4;
    ctx.stroke();


    // --------------------------------------------------------
    // 범례
'''

if anchor in content:
    content = content.replace(anchor, replacement, 1)
    print("[OK] 최신 실제 시세 강조 링 추가")
else:
    print("[WARNING] 최신 시세 강조 위치를 찾지 못했습니다.")


# ------------------------------------------------------------
# 8. 범례 스타일 변경
# ------------------------------------------------------------
legend_anchor = '''        {
            name: "실제 가격",
            color: "#2563eb"
        },
'''

legend_replacement = '''        {
            name: "실제 가격",
            color: "#2563eb",
            dashed: false
        },
'''

if legend_anchor in content:
    content = content.replace(
        legend_anchor,
        legend_replacement,
        1,
    )


for name, color in [
    ("단기 3시간", "#f59e0b"),
    ("중기 3일", "#16a34a"),
    ("장기 30일", "#9333ea"),
]:
    old = f'''        {{
            name: "{name}",
            color: "{color}"
        }},
'''

    new = f'''        {{
            name: "{name}",
            color: "{color}",
            dashed: true
        }},
'''

    if old in content:
        content = content.replace(old, new, 1)


# ------------------------------------------------------------
# 9. 범례 선도 실제/예측 스타일과 동일하게
# ------------------------------------------------------------
old_legend_draw = '''        ctx.beginPath();

        ctx.moveTo(legendX, legendY);
        ctx.lineTo(legendX + 18, legendY);

        ctx.strokeStyle = item.color;
        ctx.lineWidth = 3;
        ctx.stroke();
'''

new_legend_draw = '''        ctx.beginPath();

        ctx.moveTo(legendX, legendY);
        ctx.lineTo(legendX + 18, legendY);

        ctx.strokeStyle = item.color;
        ctx.lineWidth = item.dashed ? 2 : 4;

        if (item.dashed) {
            ctx.setLineDash([6, 4]);
        } else {
            ctx.setLineDash([]);
        }

        ctx.stroke();

        // 실제 가격 범례는 작은 점 추가
        if (!item.dashed) {
            ctx.beginPath();

            ctx.arc(
                legendX + 9,
                legendY,
                3,
                0,
                Math.PI * 2
            );

            ctx.fillStyle = item.color;
            ctx.fill();
        }

        ctx.setLineDash([]);
'''

if old_legend_draw in content:
    content = content.replace(
        old_legend_draw,
        new_legend_draw,
        1,
    )
    print("[OK] 범례 스타일 변경")


# ------------------------------------------------------------
# 저장
# ------------------------------------------------------------
HTML_FILE.write_text(content, encoding="utf-8")


# ------------------------------------------------------------
# 결과 검사
# ------------------------------------------------------------
checks = {
    "drawPredictionLine": len(
        re.findall(r"function drawPredictionLine", content)
    ),
    "drawAceGoldChart": len(
        re.findall(r"function drawAceGoldChart", content)
    ),
    "setLineDash": len(
        re.findall(r"setLineDash", content)
    ),
    "actualSeries": len(
        re.findall(r"actualSeries", content)
    ),
}


print()
print("=" * 60)
print("[SUCCESS] 그래프 스타일 패치 완료")
print("=" * 60)

for key, value in checks.items():
    print(f"{key}: {value}개")

print()
print("변경 내용:")
print("  실제 시세 : 파란색 4px 실선 + 최신값 강조")
print("  단기 예측 : 주황색 2px 점선")
print("  중기 예측 : 초록색 2px 점선")
print("  장기 예측 : 보라색 2px 점선")
print()
print(f"백업: {BACKUP_FILE}")
print(f"수정: {HTML_FILE}")
print()
print("다음 명령으로 확인:")
print("  python3 -m py_compile patch_chart_style.py")
print("  grep -n 'setLineDash\\|lineWidth = item.dashed' templates/dashboard.html")