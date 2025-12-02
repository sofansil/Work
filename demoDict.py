# demoDict.py

fruits = {"apple":"red", "banana":"yellow"}
print(len((fruits)))

#검색
print(fruits["apple"])

#입력
fruits["cherry"] = "red"
print(len((fruits)))

#삭제
del fruits["apple"]
print(fruits)
print(len((fruits)))

# 반복문 
for item in fruits.items():
        print(item)

print("key, value를 별도로 처리")

for k, v in fruits.items():
    print(k, v)
