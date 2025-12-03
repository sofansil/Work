# db1.py
import sqlite3

# 연결객체 생성
con = sqlite3.connect(":memory:")
# 커서객체 생성
cur = con.cursor()
# 테이블 생성
cur.execute("CREATE TABLE PhoneBook (name text, phoneNum text);")
# 데이터 삽입
cur.execute("INSERT INTO PhoneBook VALUES ('윤석우', '010-2782-6901');")
cur.execute("INSERT INTO PhoneBook VALUES ('김신실', '010-5455-6176');")

# 입력파라메터 처리
name = '윤지호'
phoneNum = '010-2133-6176'
cur.execute("INSERT INTO PhoneBook VALUES (?, ?);", (name, phoneNum))

# 다중의 리스트를 입력
datalist = (("윤지예", "010-6570-6176"),("윤은노","010-8662-2174"))
cur.executemany("INSERT INTO PhoneBook VALUES (?, ?);", datalist)

# 데이터 조회
cur.execute("SELECT * FROM PhoneBook")
for row in cur:
    print(row)

