# Person 클래스를 정의합니다.
class Person:
    # 생성자: id와 name을 초기화합니다.
    def __init__(self, id, name):
        self.id = id  # 사람의 고유 번호
        self.name = name  # 사람의 이름

    # 정보를 출력하는 메서드입니다.
    def printInfo(self):
        print(f"ID: {self.id}, Name: {self.name}")  # ID와 이름을 출력합니다.

# Manager 클래스를 정의합니다. Person 클래스를 상속받습니다.
class Manager(Person):
    # 생성자: id, name, title을 초기화합니다.
    def __init__(self, id, name, title):
        super().__init__(id, name)  # 부모 클래스의 생성자를 호출합니다.
        self.title = title  # 매니저의 직책

    # 정보를 출력하는 메서드입니다.
    def printInfo(self):
        super().printInfo()  # 부모 클래스의 printInfo 메서드를 호출합니다.
        print(f"Title: {self.title}")  # 직책을 출력합니다.

# Employee 클래스를 정의합니다. Person 클래스를 상속받습니다.
class Employee(Person):
    # 생성자: id, name, skill을 초기화합니다.
    def __init__(self, id, name, skill):
        super().__init__(id, name)  # 부모 클래스의 생성자를 호출합니다.
        self.skill = skill  # 직원의 기술

    # 정보를 출력하는 메서드입니다.
    def printInfo(self):
        super().printInfo()  # 부모 클래스의 printInfo 메서드를 호출합니다.
        print(f"Skill: {self.skill}")  # 기술을 출력합니다.

# 인스턴스를 생성하고 테스트하는 코드입니다.
if __name__ == "__main__":
    # 10개의 인스턴스를 생성합니다.
    people = [
        Manager(1, "Alice", "Team Lead"),
        Employee(2, "Bob", "Python"),
        Manager(3, "Charlie", "Project Manager"),
        Employee(4, "David", "Java"),
        Employee(5, "Eve", "JavaScript"),
        Manager(6, "Frank", "Department Head"),
        Employee(7, "Grace", "C#"),
        Employee(8, "Heidi", "Ruby"),
        Manager(9, "Ivan", "Senior Manager"),
        Employee(10, "Judy", "Go"),
    ]

    # 각 인스턴스의 정보를 출력합니다.
    for person in people:
        person.printInfo()  # 각 사람의 정보를 출력합니다.
        print()  # 줄 바꿈을 추가합니다.