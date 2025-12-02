# demoIndexing.py

strA = "python"
strB = "파이썬은 강력해"
strC = """
파이썬은
강력한
언어입니다.
"""

print(len(strA))
print(len(strB))
print(strC)

#슬라이싱
print(strA[0])
print(strA[1])
print((strA[0:3]))
print(strA[-2:])
print(strA[:])

#리스트 연습
colors = ["red", "blue", "green"]
print(colors)
print(len(colors))
colors.append("black")
colors.insert(1, "pink")
print(colors)

#제거
colors.remove("red")
print(colors)

#문자열과 정수를 결합
print("abcd" + str(1))

#정렬
colors.extend(["white", "blue", "yellow"])
colors.sort()
print(colors)
colors.reverse()
print(colors)
