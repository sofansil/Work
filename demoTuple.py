# demoTuple.py

t = (1,2,3)
type(t)
device= ("아이폰", "아이패드", "노트북")

def calc(a,b):
    return a+b, a*b

result = calc(5, 6)
print(result)

print("id:%s, name:%s" % ("kim", "김유신"))


args = (5,6)
print(calc(*args))


a = set((1,2,3))
print(a)
b = list(a)
b.append(10)
print(b)


