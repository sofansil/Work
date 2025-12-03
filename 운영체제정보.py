# 운영체제정보.py

import os
import os.path
import glob

print(os.name)           # 운영체제 이름 출력 (예: 'posix', 'nt', 'java')
print(os.environ)        # 환경 변수 출력

print("=== 파일정보 ===")
fileName = "C:\\Users\\sofan\\AppData\\Local\\Programs\\Python\\Python310\\Python.exe"

if os.path.exists(fileName):
    print("파일명 :", os.path.getsize(fileName), "바이트")          # 파일명
else:
    print("파일이 존재하지 않습니다.")

print("========== 파일목록 ==========")
#print(glob.glob("c:\\work\\*.py"))  # 특정 확장자의 파일 목록 출력
for item in glob.glob(r"c:\work\*.py"):
    print(item)

