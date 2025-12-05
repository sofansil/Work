# 나혼자연습.py

# ===== List (리스트) =====
print("=" * 50)
print("List (리스트)")
print("=" * 50)
lst = [1, 2, 3, 4, 5]
print(f"생성: {lst}")
print(f"타입: {type(lst)}")
print(f"길이: {len(lst)}")

# 장점: 가변성
lst.append(6)
print(f"요소 추가: {lst}")
lst[0] = 10
print(f"요소 수정: {lst}")
lst.remove(10)
print(f"요소 제거: {lst}")
print("✓ 수정 가능 (가변)")

# ===== Tuple (튜플) =====
print("\n" + "=" * 50)
print("Tuple (튜플)")
print("=" * 50)
tpl = (1, 2, 3, 4, 5)
print(f"생성: {tpl}")
print(f"타입: {type(tpl)}")
print(f"길이: {len(tpl)}")

# 장점: 불변성 (안전성, 성능)
print(f"인덱싱: tpl[0] = {tpl[0]}")
print(f"슬라이싱: tpl[1:3] = {tpl[1:3]}")
print("✓ 수정 불가능 (불변) - 데이터 보호")
print("✓ 딕셔너리 키로 사용 가능")

# 튜플을 딕셔너리 키로 사용
tuple_dict = {tpl: "튜플은 키로 사용 가능"}
print(f"키로 사용: {tuple_dict}")

# ===== Dictionary (딕셔너리) =====
print("\n" + "=" * 50)
print("Dictionary (딕셔너리)")
print("=" * 50)
dct = {"이름": "파이썬", "버전": 3.9, "인기도": 5}
print(f"생성: {dct}")
print(f"타입: {type(dct)}")
print(f"길이: {len(dct)}")

# 장점: 키-값 쌍으로 데이터 관리
print(f"접근 (키): dct['이름'] = {dct['이름']}")
dct["가격"] = "무료"
print(f"요소 추가: {dct}")
dct["버전"] = 3.10
print(f"요소 수정: {dct}")
print("✓ 키-값 쌍으로 직관적 데이터 관리")

# ===== 성능 비교 =====
print("\n" + "=" * 50)
print("성능 비교")
print("=" * 50)
import sys

lst_mem = sys.getsizeof([1, 2, 3, 4, 5])
tpl_mem = sys.getsizeof((1, 2, 3, 4, 5))
dct_mem = sys.getsizeof({"a": 1, "b": 2, "c": 3, "d": 4, "e": 5})

print(f"List 메모리: {lst_mem} bytes")
print(f"Tuple 메모리: {tpl_mem} bytes (더 효율적)")
print(f"Dict 메모리: {dct_mem} bytes")

# ===== 형변환 (Type Conversion) =====
print("\n" + "=" * 50)
print("형변환 (Type Conversion)")
print("=" * 50)

# 1. List ↔ Tuple
print("\n[1] List ↔ Tuple")
lst = [1, 2, 3, 4, 5]
print(f"원본 List: {lst}")
tpl_from_lst = tuple(lst)
print(f"List → Tuple: {tpl_from_lst}")
print(f"타입: {type(tpl_from_lst)}")

tpl = (10, 20, 30, 40, 50)
print(f"\n원본 Tuple: {tpl}")
lst_from_tpl = list(tpl)
print(f"Tuple → List: {lst_from_tpl}")
print(f"타입: {type(lst_from_tpl)}")

# 2. List ↔ Dictionary
print("\n[2] List ↔ Dictionary")
lst_pairs = [["이름", "파이썬"], ["버전", 3.9], ["인기도", 5]]
print(f"원본 List (2D): {lst_pairs}")
dct_from_lst = dict(lst_pairs)
print(f"List → Dictionary: {dct_from_lst}")
print(f"타입: {type(dct_from_lst)}")

dct = {"과목": "파이썬", "학점": "A", "학생": "김철수"}
print(f"\n원본 Dictionary: {dct}")
lst_from_dct = list(dct)  # 키만 추출
print(f"Dictionary → List (키만): {lst_from_dct}")
lst_items = list(dct.items())  # 키-값 쌍 추출
print(f"Dictionary → List (키-값): {lst_items}")

# 3. Tuple ↔ Dictionary
print("\n[3] Tuple ↔ Dictionary")
tpl_pairs = (("색상", "빨강"), ("크기", "큼"), ("가격", 5000))
print(f"원본 Tuple: {tpl_pairs}")
dct_from_tpl = dict(tpl_pairs)
print(f"Tuple → Dictionary: {dct_from_tpl}")
print(f"타입: {type(dct_from_tpl)}")

dct = {"나라": "한국", "수도": "서울", "언어": "한국어"}
print(f"\n원본 Dictionary: {dct}")
tpl_from_dct = tuple(dct.items())
print(f"Dictionary → Tuple: {tpl_from_dct}")
print(f"타입: {type(tpl_from_dct)}")

# 4. 복합 형변환
print("\n[4] 복합 형변환")
original_dct = {"A": 1, "B": 2, "C": 3}
print(f"원본: {original_dct}")
print(f"Dict → List → Tuple: {tuple(list(original_dct.items()))}")
print(f"Dict → Tuple → List: {list(tuple(original_dct.items()))}")

# 5. 실용적인 예제
print("\n[5] 실용적인 예제")
scores = [85, 90, 78, 92, 88]
print(f"List (점수): {scores}")
score_tuple = tuple(scores)
print(f"Tuple로 변환 (안전성): {score_tuple}")

student_data = [("김철수", 85), ("이영희", 90), ("박민준", 78)]
print(f"\nList (학생 데이터): {student_data}")
student_dict = dict(student_data)
print(f"Dictionary로 변환 (빠른 검색): {student_dict}")
print(f"'이영희'의 점수: {student_dict['이영희']}")
