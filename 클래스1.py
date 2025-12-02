# 클래스1.py

#1) 클래스 정의
class Person:
    # 초기화 메서드
    def __init__(self):
        self.name = "default name"
    def print(self):
        # f-string문법: 포맷 스트링
        #print("My name is {}".format(self.name))
        print(f"My name is {self.name}")

#2) 인스턴스 생성
p1 = Person()
p2 = Person()
p1.name = "전우치"

#3) 메서드 호출
p1.print()
p2.print()

