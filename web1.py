# web1.py
# 웹크롤링을 위한 선언
from bs4 import BeautifulSoup

# 파일을 로딩
page = open(r"c:\work\Chap09_test.html", "rt", encoding="utf-8").read()

# 검색이 용이한 객체 생성: 초기화
soup = BeautifulSoup(page, 'html.parser')

# 전체를 출력
#print(soup.prettify())
# <p>를 몽땅 검색
#print(soup.find_all('p'))
# print(soup.find('p'))
# 조건검색: <p class="outer-text"> 필터링
# print(soup.find_all('p', class_='outer-text'))
# attrs는 attribute의 약자
# print(soup.find_all('p', attrs={'class':'outer-text'}))

# 태그 내부의 문자열만 추출: .text
for item in soup.find_all('p'):
    title = item.text.strip()  # strip()는 앞뒤 공백제거
    title = title.replace('\n', ' ')
    print(title) 
