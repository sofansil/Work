# DemoForm.py
# DemoForm.ui(화면) + DemoForm.py(로직) = DemoForm 완성
import sys
from PyQt5.QtWidgets import *
from PyQt5 import uic

# 디자인 문서를 로딩
form_class = uic.loadUiType("DemoForm.ui")[0]

# DemoForm 클래스 정의
class DemoForm(QDialog, form_class):
    def __init__(self):
        super().__init__()
        self.setupUi(self) # 화면 로딩
        self.label.setText("첫번째 화면") # 라벨 텍스트 설정

# 진입점 체크
if __name__ == "__main__":
    # 실행 프로세스를 설정
    app = QApplication(sys.argv)
    # 폼을 생성
    demo_form = DemoForm()
    # 화면에 보이기
    demo_form.show()
    # 이벤트 루프 진입
    app.exec_()

