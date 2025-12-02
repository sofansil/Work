# 문자열 처리 메서드 연습

strA = "python programming"
strB = "파이썬은 강력해"

print(len(strA))
print(len(strB))
print(strA.capitalize())
print(strA.count("p"))

data = " spam and ham "
result = data.strip()
print(len(data))
print(data)
print(len(result))
print(result)

# 치환
result2 = result.replace("spam", "spam egg")
print(result2)

# 리스트로 분할
lst = result2.split()
print(lst)

# 문자열 합치기
joined = ":)".join(lst)
print(joined)

# 정규표현식: 특정한 패턴을 찾아서 바로 작업
import re

result = re.search("[0-9]*th", "35th")
print(result)
print(result.group())

# 단어를 검색, 특정 패턴 검색
result = re.search("apple", "this is apple")
print(result)
print(result.group())

result = re.search("\d{4}", "올해는 2025년입니다.")
print(result)
print(result.group())

