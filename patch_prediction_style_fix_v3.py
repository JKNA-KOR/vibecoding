from pathlib import Path
import shutil
import re

HTML = Path("templates/dashboard.html")
BACKUP = Path("templates/dashboard.html.before_prediction_style_fix_v3")

content = HTML.read_text(encoding="utf-8")

if not BACKUP.exists():
    shutil.copy2(HTML, BACKUP)
    print(f"[OK] 백업 생성 -> {BACKUP}")
else:
    print(f"[INFO] 기존 백업 사용 -> {BACKUP}")


# ============================================================
# 1. drawPredictionLine 교체
# ============================================================

start = content.find("function drawPredictionLine(")

if start == -1:
    print("[ERROR] drawPredictionLine을 찾지 못했습니다.")
    raise SystemExit(1)

end = content.find("\n\nfunction drawAceGoldChart(", start)

if end == -1:
    print("[ERROR] drawAceGoldChart 시작 위치를 찾지 못했습니다.")
    raise SystemExit(1)


new_line_function = r'''
function drawPredictionLine(
    ctx,
    points,
    x,
    y,
    color,
    lineWidth,
    dashed = false
) {
    if (!points || !points.length) {
        return;
    }

    ctx.save();

    ctx.globalAlpha = 1;
    ctx.setLineDash([]);

    ctx.beginPath();

    let started = false;

    points.forEach(item => {
        const date = new Date(item.timestamp);

        if (Number.isNaN(date.getTime())) {
            return;
        }

        const xx = x(date);
        const yy = y(item.price);

        if (!Number.isFinite(xx) || !Number.isFinite(yy)) {
            return;
        }

        if (!started) {
            ctx.moveTo(xx, yy);
            started = true;
        } else {
            ctx.lineTo(xx, yy);
        }
    });

    if (!started) {
        ctx.restore();
        return;
    }

    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;

    ctx.setLineDash(
        dashed ? [8, 6] : []
    );

    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.globalAlpha = 1;

    ctx.stroke();

    ctx.restore();
}
'''


content = (
    content[:start]
    + new_line_function.strip()
    + content[end:]
)

print("[OK] drawPredictionLine 교체")


# ============================================================
# 2. drawPredictionPoints 교체
# ============================================================

start = content.find("function drawPredictionPoints(")

if start == -1:
    print("[WARNING] drawPredictionPoints가 없어 새로 추가합니다.")

    insert_at = content.find("\n\nfunction drawPredictionLine(")

    if insert_at == -1:
        print("[ERROR] drawPredictionLine 삽입 위치를 찾지 못했습니다.")
        raise SystemExit(1)

    points_function = r'''
function drawPredictionPoints(
    ctx,
    points,
    x,
    y,
    color
) {
    if (!points || !points.length) {
        return;
    }

    ctx.save();

    ctx.globalAlpha = 1;
    ctx.setLineDash([]);

    points.forEach(item => {
        const date = new Date(item.timestamp);

        if (Number.isNaN(date.getTime())) {
            return;
        }

        const xx = x(date);
        const yy = y(item.price);

        if (!Number.isFinite(xx) || !Number.isFinite(yy)) {
            return;
        }

        ctx.beginPath();

        ctx.arc(
            xx,
            yy,
            3.5,
            0,
            Math.PI * 2
        );

        ctx.fillStyle = "#ffffff";
        ctx.fill();

        ctx.beginPath();

        ctx.arc(
            xx,
            yy,
            3,
            0,
            Math.PI * 2
        );

        ctx.fillStyle = color;
        ctx.fill();
    });

    ctx.restore();
}
'''

    content = (
        content[:insert_at]
        + "\n"
        + points_function.strip()
        + content[insert_at:]
    )

    print("[OK] drawPredictionPoints 추가")

else:
    end = content.find("\n\nfunction drawPredictionLine(", start)

    if end == -1:
        print("[ERROR] drawPredictionPoints 종료 위치를 찾지 못했습니다.")
        raise SystemExit(1)

    points_function = r'''
function drawPredictionPoints(
    ctx,
    points,
    x,
    y,
    color
) {
    if (!points || !points.length) {
        return;
    }

    ctx.save();

    ctx.globalAlpha = 1;
    ctx.setLineDash([]);

    points.forEach(item => {
        const date = new Date(item.timestamp);

        if (Number.isNaN(date.getTime())) {
            return;
        }

        const xx = x(date);
        const yy = y(item.price);

        if (!Number.isFinite(xx) || !Number.isFinite(yy)) {
            return;
        }

        // 흰색 외곽
        ctx.beginPath();

        ctx.arc(
            xx,
            yy,
            4.5,
            0,
            Math.PI * 2
        );

        ctx.fillStyle = "#ffffff";
        ctx.fill();

        // 예측 색상 내부 점
        ctx.beginPath();

        ctx.arc(
            xx,
            yy,
            3,
            0,
            Math.PI * 2
        );

        ctx.fillStyle = color;
        ctx.fill();
    });

    ctx.restore();
}
'''

    content = (
        content[:start]
        + points_function.strip()
        + content[end:]
    )

    print("[OK] drawPredictionPoints 교체")


# ============================================================
# 3. drawAceGoldChart 안의 선 호출 교체
# ============================================================

chart_start = content.find("function drawAceGoldChart(")

if chart_start == -1:
    print("[ERROR] drawAceGoldChart를 찾지 못했습니다.")
    raise SystemExit(1)

chart_end = content.find("\n\n// ------------------------------------------------------------\n// 반응형", chart_start)

if chart_end == -1:
    chart_end = content.find("\n\nfunction render(", chart_start)

if chart_end == -1:
    print("[ERROR] drawAceGoldChart 종료 위치를 찾지 못했습니다.")
    raise SystemExit(1)

chart = content[chart_start:chart_end]


# ------------------------------------------------------------
# 실제 가격선
# ------------------------------------------------------------

pattern_actual = re.compile(
    r'drawPredictionLine\(\s*'
    r'ctx,\s*'
    r'actualSeries,\s*'
    r'x,\s*'
    r'y,\s*'
    r'[^;]*?\n\s*\);',
    re.S
)

actual_replacement = '''drawPredictionLine(
        ctx,
        actualSeries,
        x,
        y,
        "#2563eb",
        4,
        false
    );'''

chart, n = pattern_actual.subn(
    actual_replacement,
    chart,
    count=1
)

if n:
    print("[OK] 실제 가격선 -> 굵은 실선 4px")
else:
    print("[WARNING] 실제 가격선 호출을 찾지 못했습니다.")


# ------------------------------------------------------------
# 단기
# ------------------------------------------------------------

pattern_short = re.compile(
    r'drawPredictionLine\(\s*'
    r'ctx,\s*'
    r'predictionSeries\.short,\s*'
    r'x,\s*'
    r'y,\s*'
    r'[^;]*?\n\s*\);',
    re.S
)

short_replacement = '''drawPredictionLine(
        ctx,
        predictionSeries.short,
        x,
        y,
        "#f59e0b",
        2.5,
        true
    );'''

chart, n = pattern_short.subn(
    short_replacement,
    chart,
    count=1
)

if n:
    print("[OK] 단기 예측선 -> 주황색 점선")
else:
    print("[WARNING] 단기 예측선 호출을 찾지 못했습니다.")


# ------------------------------------------------------------
# 중기
# ------------------------------------------------------------

pattern_medium = re.compile(
    r'drawPredictionLine\(\s*'
    r'ctx,\s*'
    r'predictionSeries\.medium,\s*'
    r'x,\s*'
    r'y,\s*'
    r'[^;]*?\n\s*\);',
    re.S
)

medium_replacement = '''drawPredictionLine(
        ctx,
        predictionSeries.medium,
        x,
        y,
        "#16a34a",
        2.5,
        true
    );'''

chart, n = pattern_medium.subn(
    medium_replacement,
    chart,
    count=1
)

if n:
    print("[OK] 중기 예측선 -> 초록색 점선")
else:
    print("[WARNING] 중기 예측선 호출을 찾지 못했습니다.")


# ------------------------------------------------------------
# 장기
# ------------------------------------------------------------

pattern_long = re.compile(
    r'drawPredictionLine\(\s*'
    r'ctx,\s*'
    r'predictionSeries\.long,\s*'
    r'x,\s*'
    r'y,\s*'
    r'[^;]*?\n\s*\);',
    re.S
)

long_replacement = '''drawPredictionLine(
        ctx,
        predictionSeries.long,
        x,
        y,
        "#9333ea",
        2.5,
        true
    );'''

chart, n = pattern_long.subn(
    long_replacement,
    chart,
    count=1
)

if n:
    print("[OK] 장기 예측선 -> 보라색 점선")
else:
    print("[WARNING] 장기 예측선 호출을 찾지 못했습니다.")


content = (
    content[:chart_start]
    + chart
    + content[chart_end:]
)


# ============================================================
# 4. 실제 가격 최신점 강조
# ============================================================

chart_start = content.find("function drawAceGoldChart(")
chart_end = content.find("\n\n// ------------------------------------------------------------\n// 반응형", chart_start)

if chart_end == -1:
    chart_end = content.find("\n\nfunction render(", chart_start)

chart = content[chart_start:chart_end]

latest_pattern = re.compile(
    r'const latest\s*=\s*'
    r'actualSeries\[actualSeries\.length\s*-\s*1\];'
    r'.*?'
    r'(?=\n\s*//\s*=+\s*\n|\n\s*if\s*\(info\))',
    re.S
)

latest_block = r'''
const latest =
        actualSeries[actualSeries.length - 1];

    if (latest) {
        const latestX = x(new Date(latest.timestamp));
        const latestY = y(latest.price);

        ctx.save();

        ctx.globalAlpha = 1;
        ctx.setLineDash([]);

        // 외곽 강조 링
        ctx.beginPath();

        ctx.arc(
            latestX,
            latestY,
            9,
            0,
            Math.PI * 2
        );

        ctx.fillStyle = "rgba(37, 99, 235, 0.15)";
        ctx.fill();

        // 흰색 테두리
        ctx.beginPath();

        ctx.arc(
            latestX,
            latestY,
            6,
            0,
            Math.PI * 2
        );

        ctx.fillStyle = "#ffffff";
        ctx.fill();

        // 실제 가격 점
        ctx.beginPath();

        ctx.arc(
            latestX,
            latestY,
            4.5,
            0,
            Math.PI * 2
        );

        ctx.fillStyle = "#2563eb";
        ctx.fill();

        ctx.restore();
    }

'''

if "const latest =" in chart and "latestX" in chart:
    chart = re.sub(
        r'const latest\s*=\s*actualSeries\[actualSeries\.length\s*-\s*1\];.*?(?=\n\s*//|\n\s*if\s*\(info\))',
        latest_block,
        chart,
        count=1,
        flags=re.S
    )
    print("[OK] 실제 최신 가격 강조점 적용")


# ============================================================
# 5. 범례를 실제 선 스타일과 동일하게
# ============================================================

legend_pattern = re.compile(
    r'const legend\s*=\s*\[.*?\];',
    re.S
)

legend_replacement = r'''const legend = [
        {
            name: "실제 가격",
            color: "#2563eb",
            dashed: false,
            width: 4
        },
        {
            name: "단기 3시간",
            color: "#f59e0b",
            dashed: true,
            width: 2.5
        },
        {
            name: "중기 3일",
            color: "#16a34a",
            dashed: true,
            width: 2.5
        },
        {
            name: "장기 30일",
            color: "#9333ea",
            dashed: true,
            width: 2.5
        }
    ];'''

chart, n = legend_pattern.subn(
    legend_replacement,
    chart,
    count=1
)

if n:
    print("[OK] 범례 데이터 교체")


# 범례 line 렌더링에서 dashed 적용
legend_line_pattern = re.compile(
    r'ctx\.beginPath\(\);\s*'
    r'ctx\.moveTo\(legendX, legendY\);\s*'
    r'ctx\.lineTo\(legendX \+ 18, legendY\);\s*'
    r'ctx\.strokeStyle = item\.color;\s*'
    r'ctx\.lineWidth = 3;\s*'
    r'ctx\.stroke\(\);',
    re.S
)

legend_line_replacement = r'''ctx.save();

        ctx.globalAlpha = 1;

        ctx.beginPath();

        ctx.moveTo(legendX, legendY);
        ctx.lineTo(legendX + 18, legendY);

        ctx.strokeStyle = item.color;
        ctx.lineWidth = item.width;

        ctx.setLineDash(
            item.dashed ? [6, 4] : []
        );

        ctx.lineCap = "round";
        ctx.stroke();

        ctx.restore();'''

chart, n = legend_line_pattern.subn(
    legend_line_replacement,
    chart,
    count=1
)

if n:
    print("[OK] 범례 점선 스타일 적용")
else:
    print("[WARNING] 범례 렌더링 코드를 찾지 못했습니다.")


content = (
    content[:chart_start]
    + chart
    + content[chart_end:]
)


# ============================================================
# 6. 문법/중복 검사
# ============================================================

checks = {
    "getPredictionSeries": len(re.findall(r"function getPredictionSeries\s*\(", content)),
    "drawPredictionLine": len(re.findall(r"function drawPredictionLine\s*\(", content)),
    "drawPredictionPoints": len(re.findall(r"function drawPredictionPoints\s*\(", content)),
    "drawAceGoldChart": len(re.findall(r"function drawAceGoldChart\s*\(", content)),
    "goldChartData": len(re.findall(r"\bgoldChartData\b", content)),
    "goldPredictionData": len(re.findall(r"\bgoldPredictionData\b", content)),
}

print()
print("==========================================")
print("그래프 스타일 패치 검사")
print("==========================================")

for key, value in checks.items():
    print(f"{key}: {value}개")


if checks["drawPredictionLine"] != 1:
    print("[ERROR] drawPredictionLine 중복/누락")
    raise SystemExit(1)

if checks["drawPredictionPoints"] != 1:
    print("[ERROR] drawPredictionPoints 중복/누락")
    raise SystemExit(1)

if checks["drawAceGoldChart"] != 1:
    print("[ERROR] drawAceGoldChart 중복/누락")
    raise SystemExit(1)


HTML.write_text(content, encoding="utf-8")

print()
print("[SUCCESS] 그래프 스타일 패치 완료")
print()
print("적용 내용:")
print("  실제 가격 : 굵은 파란색 실선 4px")
print("  단기 예측 : 주황색 점선 2.5px + 포인트")
print("  중기 예측 : 초록색 점선 2.5px + 포인트")
print("  장기 예측 : 보라색 점선 2.5px + 포인트")
print("  실제 최신값 : 강조 원")
print("  예측 포인트 : 흰색 외곽 + 색상 내부")
print("  canvas 상태 자동 초기화")
print()
print(f"백업: {BACKUP}")
