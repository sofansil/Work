# class2.py
# Developer 클래스를 정의하려고 하는데, id, name, skill 속성을 추가

class Developer:
    def __init__(self, id, name, skill):
        self.id = id  # 개발자의 고유 번호
        self.name = name  # 개발자의 이름
        self.skill = skill  # 개발자의 기술

    def get_info(self):
        print(f"ID: {self.id}, Name: {self.name}, Skill: {self.skill}")  # 개발자의 정보를 출력

# 인스턴스를 생성
dev = Developer(1, "Alice", "Python")
print(dev.get_info())  # 개발자의 정보를 출력합니다.

