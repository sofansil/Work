# web2.py
# 웹크롤링을 위한 선언
from bs4 import BeautifulSoup
# 웹서버에 요청
import urllib.request

# 파일로 저장
f = open("clien.txt", "wt", encoding="utf-8")

for i in range(0,10):
    print("페이지:", i+1)
    f.write("페이지:" + str(i+1) + "\n")
    
    # 주소
    url = "https://www.clien.net/service/board/sold?&od=T31&category=0&po=" + str(i)
    print(url)

    # 페이지 실행 결과를 문자열로 받기
    page = urllib.request.urlopen(url).read()
    # 검색이 용이한 객체
    soup = BeautifulSoup(page, 'html.parser')

    lst = soup.find_all("span", attrs={"data-role":"list-title-text"})
    for tag in lst:
        title = tag.text.strip()
        print(title)
        f.write(title + "\n")

# 마지막에 파일 닫기
f.close()


# <span class="subject_fixed" data-role="list-title-text" title="(끌어올림) 맥북프로 M3pro 14인치">
# 	(끌어올림) 맥북프로 M3pro 14인치
# </span>