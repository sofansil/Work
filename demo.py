# demo.py

print("Hello VS Code");

lst = [1,2,3,4,5]
for i in lst:
    print(i)

# List, Tuple, Set, Dict 비교 예제

# -------------------------------
# 1) 자료형 생성
# -------------------------------
my_list = [1, 2, 2, 3]
my_tuple = (1, 2, 2, 3)
my_set = {1, 2, 2, 3}
my_dict = {"a": 1, "b": 2, "c": 3}

print("=== 자료형 기본 출력 ===")
print("List :", my_list)
print("Tuple:", my_tuple)
print("Set  :", my_set)       # 중복 제거됨
print("Dict :", my_dict)
print()

# -------------------------------
# 2) 수정 가능 여부
# -------------------------------
print("=== 수정 가능 여부 테스트 ===")
my_list[0] = 100
print("List 수정:", my_list)

try:
    my_tuple[0] = 100
except TypeError:
    print("Tuple 수정: 불가능 (TypeError 발생)")

# set 수정 → add/remove 사용
my_set.add(100)
print("Set 수정(add):", my_set)

# dict 수정 → key로 접근
my_dict["a"] = 100
print("Dict 수정:", my_dict)
print()

# -------------------------------
# 3) 순서 유지 여부
# -------------------------------
print("=== 순서 유지 여부 ===")
print("List 순서:", my_list)
print("Tuple 순서:", my_tuple)
print("Set 순서:", my_set, "(정렬/순서 보장 안됨)")
print("Dict 순서:", my_dict, "(파이썬 3.7+ 이후 삽입 순서 유지)")
print()

# -------------------------------
# 4) 주요 기능 비교
# -------------------------------
print("=== 주요 기능 예제 ===")

# List: append, pop 등
my_list.append(999)
print("List append:", my_list)

# Tuple: count, index 사용 가능
print("Tuple count(2):", my_tuple.count(2))

# Set: 교집합, 합집합 등
set2 = {2, 3, 4}
print("Set 교집합:", my_set & set2)
print("Set 합집합:", my_set | set2)

# Dict: keys, values, items
print("Dict keys  :", my_dict.keys())
print("Dict values:", my_dict.values())
print("Dict items :", my_dict.items())
