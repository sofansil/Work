class Person:
    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name

    def printInfo(self):
        print(f"Person  - ID: {self.id}, Name: {self.name}")


class Manager(Person):
    def __init__(self, id: int, name: str, title: str):
        super().__init__(id, name)
        self.title = title

    def printInfo(self):
        print(f"Manager - ID: {self.id}, Name: {self.name}, Title: {self.title}")


class Employee(Person):
    def __init__(self, id: int, name: str, skill: str):
        super().__init__(id, name)
        self.skill = skill

    def printInfo(self):
        print(f"Employee- ID: {self.id}, Name: {self.name}, Skill: {self.skill}")


if __name__ == "__main__":
    people = [
        Person(1, "Alice"),
        Manager(2, "Bob", "Sales Manager"),
        Employee(3, "Charlie", "Python"),
        Person(4, "Diana"),
        Manager(5, "Evan", "HR Manager"),
        Employee(6, "Fiona", "Java"),
        Employee(7, "George", "C++"),
        Person(8, "Hannah"),
        Manager(9, "Ian", "CTO"),
        Employee(10, "Julia", "JavaScript"),
    ]

    for p in people:
        p.printInfo()
```# filepath: c:\Work\people.py
class Person:
    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name

    def printInfo(self):
        print(f"Person  - ID: {self.id}, Name: {self.name}")


class Manager(Person):
    def __init__(self, id: int, name: str, title: str):
        super().__init__(id, name)
        self.title = title

    def printInfo(self):
        print(f"Manager - ID: {self.id}, Name: {self.name}, Title: {self.title}")


class Employee(Person):
    def __init__(self, id: int, name: str, skill: str):
        super().__init__(id, name)
        self.skill = skill

    def printInfo(self):
        print(f"Employee- ID: {self.id}, Name: {self.name}, Skill: {self.skill}")


if __name__ == "__main__":
    people = [
        Person(1, "Alice"),
        Manager(2, "Bob", "Sales Manager"),
        Employee(3, "Charlie", "Python"),
        Person(4, "Diana"),
        Manager(5, "Evan", "HR Manager"),
        Employee(6, "Fiona", "Java"),
        Employee(7, "George", "C++"),
        Person(8, "Hannah"),
        Manager(9, "Ian", "CTO"),
        Employee(10, "Julia", "JavaScript"),
    ]

    for p in people:
        p.printInfo()