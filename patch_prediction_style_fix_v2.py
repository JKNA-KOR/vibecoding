from pathlib import Path
import re
import shutil
import sys


HTML = Path("templates/dashboard.html")
BACKUP = Path("templates/dashboard.html.before_prediction_style_fix_v2")


if not HTML.exists():
    print("[ERROR] templates/dashboard.html 파일이 없습니다.")
    sys.exit(1)


# ------------------------------------------------------------
# 백업
# ------------------------------------------------------------
if not BACKUP.exists():
    shutil.copy2(HTML, BACKUP)
    print(f"[OK] 백업 생성 -> {BACKUP}")
else:
    print(f"[INFO] 기존 백업 사용 -> {BACKUP}")


content = HTML.read_text(encoding="utf-8")


# ============================================================
# 1. drawPredictionLine 함수 교체
#
# 실제 가격:
#   굵은 실선
#
# 예측:
#   점선
#
# globalAlpha를 항상 1로 초기화하여
# 이전 canvas 상태가 다음 선에 영향을 주지 않도록 한다.
# ============================================================

line_start = content.find("function drawPredictionLine(")

if line_start == -1:
    print("[ERROR] drawPredictionLine 함수를 찾을 수 없습니다.")
    sys.exit(1)


# 함수 끝을 찾는다.
brace_start = content.find("{", line_start)

if brace_start == -1:
    print("[ERROR] drawPredictionLine 시작 괄호를 찾을 수 없습니다.")
    sys.exit(1)


depth = 0
line_end = None

for i in range(brace_start, len(content)):
    ch = content[i]

    if ch == "{":
        depth += 1
    elif ch == "}":
        depth -= 1

        if depth == 0:
            line_end = i + 1
            break


if line_end is None:
    print("[ERROR] drawPredictionLine 종료 위치를 찾을 수 없습니다.")
    sys.exit(1)


new_draw_prediction_line = r'''
function drawPredictionLine(
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
    if (!points || !points.length) {
        return;
    }

    // 이전 canvas 상태 초기화
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
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;
        return;
    }

    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;

    // 실제 가격 = 실선
    // 예측 = 점선
    ctx.setLineDash(
        dashed
            ? [7, 5]
            : []
    );

    ctx.lineJoin = "round";
    ctx.lineCap = "round";

    ctx.globalAlpha = 1;

    ctx.stroke();

    // 다음 그래픽에 영향이 없도록 초기화
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;
}
'''.strip()


content = (
    content[:line_start]
    + new_draw_prediction_line
    + content[line_end:]
)

print("[OK] drawPredictionLine 스타일 교체")


# ============================================================
# 2. 실제 가격선
#    굵은 실선 4px
# ============================================================

actual_pattern = re.compile(
    r'("#2563eb"\s*,\s*)2\.5\s*\)'
)

content, actual_count = actual_pattern.subn(
    r'\g<1>4, false)',
    content,
    count=1,
)

if actual_count:
    print("[OK] 실제 가격선 -> 4px 실선")
else:
    print("[WARNING] 실제 가격선 호출을 찾지 못했습니다.")


# ============================================================
# 3. 단기 / 중기 / 장기 예측선
#    2.5px 점선
# ============================================================

prediction_styles = {
    "#f59e0b": "단기",
    "#16a34a": "중기",
    "#9333ea": "장기",
}


for color, name in prediction_styles.items():

    pattern = re.compile(
        rf'("{re.escape(color)}"\s*,\s*)2\s*\)'
    )

    content, count = pattern.subn(
        r'\g<1>2.5, true)',
        content,
        count=1,
    )

    if count:
        print(f"[OK] {name} 예측선 -> 2.5px 점선")
    else:
        # 이미 2.5px일 가능성
        pattern2 = re.compile(
            rf'("{re.escape(color)}"\s*,\s*)2\.5\s*\)'
        )

        content, count2 = pattern2.subn(
            r'\g<1>2.5, true)',
            content,
            count=1,
        )

        if count2:
            print(f"[OK] {name} 예측선 -> 2.5px 점선")
        else:
            print(f"[WARNING] {name} 예측선 호출을 찾지 못했습니다.")


# ============================================================
# 4. drawPredictionPoints 함수가 있다면 스타일 보정
#
# 실제 가격:
#   큰 점
#
# 예측:
#   작은 점
#
# 함수가 없으면 생성하지 않는다.
# 현재 파일에 이미 존재하므로 중복 선언 방지.
# ============================================================

points_start = content.find("function drawPredictionPoints(")

if points_start == -1:
    print("[WARNING] drawPredictionPoints 함수가 없습니다.")
    print("         현재 그래프에서는 선 스타일만 적용합니다.")
else:
    print("[OK] 기존 drawPredictionPoints 함수 확인")


# ============================================================
# 5. legend도 실제/예측 구분이 명확하도록 보정
# ============================================================

# 실제 가격 legend
content = content.replace(
    '''
        {
            name: "실제 가격",
            color: "#2563eb"
        },
''',
    '''
        {
            name: "실제 가격",
            color: "#2563eb",
            dashed: false,
            lineWidth: 4
        },
''',
    1
)

# 단기
content = content.replace(
    '''
        {
            name: "단기 3시간",
            color: "#f59e0b"
        },
''',
    '''
        {
            name: "단기 3시간",
            color: "#f59e0b",
            dashed: true,
            lineWidth: 2.5
        },
''',
    1
)

# 중기
content = content.replace(
    '''
        {
            name: "중기 3일",
            color: "#16a34a"
        },
''',
    '''
        {
            name: "중기 3일",
            color: "#16a34a",
            dashed: true,
            lineWidth: 2.5
        },
''',
    1
)

# 장기
content = content.replace(
    '''
        {
            name: "장기 30일",
            color: "#9333ea"
        }
''',
    '''
        {
            name: "장기 30일",
            color: "#9333ea",
            dashed: true,
            lineWidth: 2.5
        }
''',
    1
)


# ============================================================
# 6. legend 렌더링도 점선 지원
# ============================================================

legend_line_pattern = re.compile(
    r'''
    ctx\.beginPath\(\);

    ctx\.moveTo\(legendX, legendY\);
    ctx\.lineTo\(legendX \+ 18, legendY\);

    ctx\.strokeStyle = item\.color;
    ctx\.lineWidth = 3;
    ctx\.stroke\(\);
    ''',
    re.VERBOSE,
)

legend_replacement = r'''
        ctx.beginPath();

        ctx.moveTo(legendX, legendY);
        ctx.lineTo(legendX + 18, legendY);

        ctx.strokeStyle = item.color;
        ctx.lineWidth = item.lineWidth || 3;

        ctx.setLineDash(
            item.dashed
                ? [5, 3]
                : []
        );

        ctx.globalAlpha = 1;

        ctx.stroke();

        ctx.setLineDash([]);
        ctx.globalAlpha = 1;
'''

content, legend_count = legend_line_pattern.subn(
    legend_replacement,
    content,
    count=1,
)

if legend_count:
    print("[OK] 범례도 실제=실선 / 예측=점선으로 변경")
else:
    print("[WARNING] 범례 렌더링 코드를 찾지 못했습니다.")


# ============================================================
# 7. JavaScript 기본 문법에 영향을 주는 중복 선언 확인
# ============================================================

checks = {
    "drawPredictionLine": len(
        re.findall(r'function\s+drawPredictionLine\s*\(', content)
    ),
    "drawPredictionPoints": len(
        re.findall(r'function\s+drawPredictionPoints\s*\(', content)
    ),
    "drawAceGoldChart": len(
        re.findall(r'function\s+drawAceGoldChart\s*\(', content)
    ),
    "goldChartData": len(
        re.findall(r'\b(?:let|const|var)\s+goldChartData\s*=', content)
    ),
    "goldPredictionData": len(
        re.findall(r'\b(?:let|const|var)\s+goldPredictionData\s*=', content)
    ),
}


print()
print("==========================================")
print("그래프 스타일 패치 검사")
print("==========================================")

for name, count in checks.items():
    print(f"{name}: {count}개")


# 중복 선언 검사
for name in (
    "drawPredictionLine",
    "drawPredictionPoints",
    "drawAceGoldChart",
    "goldChartData",
    "goldPredictionData",
):
    if checks[name] > 1:
        print(
            f"[ERROR] {name} 중복 선언 발견: {checks[name]}개"
        )
        sys.exit(1)


# ============================================================
# 저장
# ============================================================

HTML.write_text(content, encoding="utf-8")

print()
print("==========================================")
print("[SUCCESS] 그래프 스타일 패치 완료")
print("==========================================")
print()
print("적용 내용:")
print("  실제 가격 : 굵은 실선 4px")
print("  단기 예측 : 점선 2.5px")
print("  중기 예측 : 점선 2.5px")
print("  장기 예측 : 점선 2.5px")
print("  globalAlpha 초기화")
print("  canvas setLineDash 초기화")
print("  범례도 동일한 스타일")
print()
print(f"백업: {BACKUP}")
print()
print("다음 명령:")
print("  python3 -m py_compile patch_prediction_style_fix_v2.py")
print("  grep -n 'drawPredictionLine' templates/dashboard.html")
print("  grep -n 'drawPredictionPoints' templates/dashboard.html")
