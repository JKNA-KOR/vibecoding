from pathlib import Path
import shutil
import re
import subprocess
import sys

HTML = Path("templates/dashboard.html")
BACKUP = Path("templates/dashboard.html.before_duplicate_chart_fix")

if not HTML.exists():
    print("[ERROR] templates/dashboard.html 파일이 없습니다.")
    sys.exit(1)

text = HTML.read_text(encoding="utf-8")

# ------------------------------------------------------------
# 1. 백업
# ------------------------------------------------------------
if not BACKUP.exists():
    shutil.copy2(HTML, BACKUP)
    print(f"[OK] 백업 생성 -> {BACKUP}")
else:
    print(f"[INFO] 기존 백업 사용 -> {BACKUP}")

# ------------------------------------------------------------
# 2. 현재 중복 상태 확인
# ------------------------------------------------------------
gold_count = len(re.findall(r"\blet\s+goldChartData\s*=", text))
draw_count = len(re.findall(r"\bfunction\s+drawAceGoldChart\s*\(", text))

print(f"[INFO] goldChartData 선언 수 : {gold_count}")
print(f"[INFO] drawAceGoldChart 함수 수 : {draw_count}")

if gold_count <= 1 and draw_count <= 1:
    print("[OK] 중복 그래프 코드가 없습니다.")
    sys.exit(0)

# ------------------------------------------------------------
# 3. 첫 번째 기존 단일 그래프 JS 제거
#
# 기존 구조:
#
# let goldChartData = [];
# ...
# function drawAceGoldChart(data) {
# ...
# }
# ...
# window resize ...
#
# 새 4선 그래프는 두 번째 선언부터 시작하므로
# 첫 번째 그래프 블록을 제거합니다.
# ------------------------------------------------------------

first_decl = text.find("let goldChartData = [];")
second_decl = text.find(
    "let goldChartData = [];",
    first_decl + len("let goldChartData = [];")
)

if first_decl == -1 or second_decl == -1:
    print("[ERROR] 중복 goldChartData 위치를 찾지 못했습니다.")
    sys.exit(1)

# 첫 번째 그래프 블록 앞쪽부터 두 번째 선언 직전까지 제거.
#
# 단, HTML 구조 자체를 훼손하지 않도록
# <script> 태그는 유지해야 합니다.
#
# 첫 번째 선언이 들어있는 script의 시작 위치를 찾습니다.
script_start = text.rfind("<script", 0, first_decl)

if script_start == -1:
    print("[ERROR] 첫 번째 그래프의 <script> 시작 위치를 찾지 못했습니다.")
    sys.exit(1)

# 두 번째 선언 이후의 코드는 유지.
# 첫 번째 그래프 JS가 들어간 script를 통째로 제거하면
# 같은 script 안의 다른 코드까지 삭제될 수 있으므로
# 첫 번째 선언부터 두 번째 선언 직전까지만 제거합니다.

text = (
    text[:first_decl]
    + text[second_decl:]
)

print("[OK] 첫 번째 중복 그래프 JavaScript 제거 완료")

# ------------------------------------------------------------
# 4. 결과 검증
# ------------------------------------------------------------
gold_count_after = len(
    re.findall(r"\blet\s+goldChartData\s*=", text)
)

draw_count_after = len(
    re.findall(r"\bfunction\s+drawAceGoldChart\s*\(", text)
)

prediction_count = len(
    re.findall(r"\bfunction\s+getPredictionSeries\s*\(", text)
)

prediction_series_count = text.count("prediction_series")

print()
print("===== 검증 결과 =====")
print(f"goldChartData 선언 : {gold_count_after}")
print(f"drawAceGoldChart 함수 : {draw_count_after}")
print(f"getPredictionSeries 함수 : {prediction_count}")
print(f"prediction_series 문자열 : {prediction_series_count}")

if gold_count_after != 1:
    print("[ERROR] goldChartData 중복이 아직 존재합니다.")
    sys.exit(1)

if draw_count_after != 1:
    print("[ERROR] drawAceGoldChart 중복이 아직 존재합니다.")
    sys.exit(1)

if prediction_count != 1:
    print("[WARNING] getPredictionSeries() 확인 필요")

if prediction_series_count < 1:
    print("[ERROR] prediction_series가 사라졌습니다.")
    sys.exit(1)

HTML.write_text(text, encoding="utf-8")

print()
print("==============================================")
print("[SUCCESS] 중복 그래프 JavaScript 제거 완료")
print("==============================================")
print(f"수정 파일 : {HTML}")
print(f"백업 파일 : {BACKUP}")
print()
print("다음 명령으로 확인:")
print('grep -n "goldChartData" templates/dashboard.html')
print('grep -n "drawAceGoldChart" templates/dashboard.html')
print('grep -n "getPredictionSeries" templates/dashboard.html')
