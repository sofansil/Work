# DemoForm2.py
# DemoForm2.ui(화면) + DemoForm2.py(로직) = DemoForm2 완성
import sys
from PyQt5.QtWidgets import *
from PyQt5 import uic
# 웹크롤링을 위한 선언
from bs4 import BeautifulSoup
# 웹서버에 요청
import urllib.request

# 디자인 문서를 로딩(로딩하는 화면을 변경)
form_class = uic.loadUiType("DemoForm2.ui")[0]

# DemoForm2 클래스 정의(상복받는 부모 - QMainWindow)
class DemoForm2(QMainWindow, form_class):
    def __init__(self):
        super().__init__()
        self.setupUi(self) # 화면 로딩
        
    # 슬롯 매서드 추가
    def firstClick(self):

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

        self.label.setText("클리앙 중고장터 크롤링 완료")
    def secondClick(self):
        self.label.setText("두 번째 버튼 클릭")
    def thirdClick(self):
        self.label.setText("세 번째 버튼 클릭")

# 진입점 체크
if __name__ == "__main__":
    # 실행 프로세스를 설정
    app = QApplication(sys.argv)
    # 폼을 생성
    demo_form = DemoForm2()
    # 화면에 보이기
    demo_form.show()
    # 이벤트 루프 진입
    app.exec_()

