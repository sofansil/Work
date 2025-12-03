# 날짜시간연습.py

import time

# 선택한 블럭을 주석처리: ctrl + /
# print(time.time())

# #일부러 대기시간 10초
# time.sleep(10)
# print(time.time())
# print(time.gmtime())
# print(time.localtime())

import datetime

d1 = datetime.date.today()
print(d1)
d2 = datetime.datetime.now()
print(d2)
d3 = datetime.datetime(2025, 12, 25)
print(d3)

# 날짜 간격 계산
d4 = datetime.timedelta(days=100)
print(d2 + d4)

# 랜덤모듈
import random

print(random.random())  # 0.0 ~ 1.0 미만의 실수
print(random.uniform(0,10))  # 0.0 ~ 1.0 미만의 실수
print(random.randint(1, 10))  # 1 ~ 10 사이의 정수
print(random.choice(['가위', '바위', '보']))  # 리스트에서 임의의 값 선택
print(random.sample(range(1, 46), 6))  # 1~45 사이의 숫자 중 6개를 임의로 선택

