import sys
import sqlite3
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTableWidget, QTableWidgetItem, QMessageBox)
from PyQt5.QtCore import Qt

class ProductManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_db()
        self.init_ui()
        self.apply_styles()
        self.selected_row = None
        
    def init_db(self):
        """데이터베이스 초기화"""
        self.conn = sqlite3.connect('MyProducts.db')
        self.cursor = self.conn.cursor()
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS Products (
                prodID INTEGER PRIMARY KEY AUTOINCREMENT,
                prodName TEXT NOT NULL,
                prodPrice INTEGER NOT NULL
            )
        ''')
        self.conn.commit()
    
    def apply_styles(self):
        """스타일 적용"""
        self.setStyleSheet('''
            QMainWindow {
                background-color: #f0f0f0;
            }
            QLabel {
                font-size: 12px;
                font-weight: bold;
                color: #333333;
            }
            QLineEdit {
                padding: 8px;
                border: 2px solid #cccccc;
                border-radius: 5px;
                font-size: 12px;
                background-color: white;
            }
            QLineEdit:focus {
                border: 2px solid #4CAF50;
                background-color: #f9f9f9;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QTableWidget {
                border: 1px solid #cccccc;
                border-radius: 5px;
                background-color: white;
                gridline-color: #eeeeee;
            }
            QTableWidget::item {
                padding: 5px;
                border: none;
            }
            QHeaderView::section {
                background-color: #4CAF50;
                color: white;
                padding: 5px;
                border: none;
                font-weight: bold;
            }
        ''')
    
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle('전자제품 관리 프로그램')
        self.setGeometry(100, 100, 800, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 입력 영역
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)
        
        input_layout.addWidget(QLabel('제품명:'))
        self.prod_name_input = QLineEdit()
        self.prod_name_input.setPlaceholderText('제품명을 입력하세요')
        input_layout.addWidget(self.prod_name_input)
        
        input_layout.addWidget(QLabel('가격:'))
        self.prod_price_input = QLineEdit()
        self.prod_price_input.setPlaceholderText('가격을 입력하세요')
        input_layout.addWidget(self.prod_price_input)
        
        # 버튼 영역
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        add_btn = QPushButton('입력')
        add_btn.clicked.connect(self.add_product)
        add_btn.setMinimumWidth(80)
        button_layout.addWidget(add_btn)
        
        update_btn = QPushButton('수정')
        update_btn.clicked.connect(self.update_product)
        update_btn.setMinimumWidth(80)
        button_layout.addWidget(update_btn)
        
        delete_btn = QPushButton('삭제')
        delete_btn.clicked.connect(self.delete_product)
        delete_btn.setMinimumWidth(80)
        delete_btn.setStyleSheet('''
            QPushButton {
                background-color: #f44336;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #ba0000;
            }
        ''')
        button_layout.addWidget(delete_btn)
        
        search_btn = QPushButton('검색')
        search_btn.clicked.connect(self.search_product)
        search_btn.setMinimumWidth(80)
        search_btn.setStyleSheet('''
            QPushButton {
                background-color: #2196F3;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:pressed {
                background-color: #0056b3;
            }
        ''')
        button_layout.addWidget(search_btn)
        
        clear_btn = QPushButton('초기화')
        clear_btn.clicked.connect(self.clear_input)
        clear_btn.setMinimumWidth(80)
        clear_btn.setStyleSheet('''
            QPushButton {
                background-color: #ff9800;
            }
            QPushButton:hover {
                background-color: #e68900;
            }
            QPushButton:pressed {
                background-color: #cc8200;
            }
        ''')
        button_layout.addWidget(clear_btn)
        
        # 테이블 영역
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(['제품ID', '제품명', '가격'])
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 300)
        self.table.setColumnWidth(2, 150)
        self.table.doubleClicked.connect(self.load_row_data)
        self.table.setAlternatingRowColors(True)
        
        # 레이아웃 조합
        main_layout.addLayout(input_layout)
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.table)
        
        central_widget.setLayout(main_layout)
        
        # 초기 데이터 로드
        self.load_all_products()
    
    def add_product(self):
        """제품 추가"""
        name = self.prod_name_input.text().strip()
        price = self.prod_price_input.text().strip()
        
        if not name or not price:
            QMessageBox.warning(self, '경고', '제품명과 가격을 입력하세요.')
            return
        
        try:
            price = int(price)
            self.cursor.execute('INSERT INTO Products (prodName, prodPrice) VALUES (?, ?)',
                              (name, price))
            self.conn.commit()
            QMessageBox.information(self, '성공', '제품이 추가되었습니다.')
            self.clear_input()
            self.load_all_products()
        except ValueError:
            QMessageBox.warning(self, '오류', '가격은 숫자여야 합니다.')
    
    def update_product(self):
        """제품 수정"""
        name = self.prod_name_input.text().strip()
        price = self.prod_price_input.text().strip()
        
        if self.selected_row is None:
            QMessageBox.warning(self, '경고', '수정할 제품을 선택하세요.')
            return
        
        if not name or not price:
            QMessageBox.warning(self, '경고', '제품명과 가격을 입력하세요.')
            return
        
        try:
            price = int(price)
            prod_id = int(self.table.item(self.selected_row, 0).text())
            self.cursor.execute('UPDATE Products SET prodName = ?, prodPrice = ? WHERE prodID = ?',
                              (name, price, prod_id))
            self.conn.commit()
            QMessageBox.information(self, '성공', '제품이 수정되었습니다.')
            self.clear_input()
            self.load_all_products()
        except ValueError:
            QMessageBox.warning(self, '오류', '가격은 숫자여야 합니다.')
    
    def delete_product(self):
        """제품 삭제"""
        if self.selected_row is None:
            QMessageBox.warning(self, '경고', '삭제할 제품을 선택하세요.')
            return
        
        prod_id = int(self.table.item(self.selected_row, 0).text())
        reply = QMessageBox.question(self, '확인', '정말 삭제하시겠습니까?',
                                     QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.cursor.execute('DELETE FROM Products WHERE prodID = ?', (prod_id,))
            self.conn.commit()
            QMessageBox.information(self, '성공', '제품이 삭제되었습니다.')
            self.clear_input()
            self.load_all_products()
    
    def search_product(self):
        """제품 검색"""
        name = self.prod_name_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, '경고', '검색할 제품명을 입력하세요.')
            return
        
        self.cursor.execute('SELECT * FROM Products WHERE prodName LIKE ?', ('%' + name + '%',))
        rows = self.cursor.fetchall()
        
        self.table.setRowCount(0)
        for row in rows:
            self.insert_table_row(row)
    
    def load_all_products(self):
        """모든 제품 로드"""
        self.cursor.execute('SELECT * FROM Products')
        rows = self.cursor.fetchall()
        
        self.table.setRowCount(0)
        for row in rows:
            self.insert_table_row(row)
        
        self.selected_row = None
    
    def insert_table_row(self, row):
        """테이블에 행 추가"""
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)
        
        for col, data in enumerate(row):
            self.table.setItem(row_position, col, QTableWidgetItem(str(data)))
    
    def load_row_data(self):
        """테이블 행 더블클릭 시 데이터 로드"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.selected_row = current_row
            prod_name = self.table.item(current_row, 1).text()
            prod_price = self.table.item(current_row, 2).text()
            
            self.prod_name_input.setText(prod_name)
            self.prod_price_input.setText(prod_price)
    
    def clear_input(self):
        """입력창 초기화"""
        self.prod_name_input.clear()
        self.prod_price_input.clear()
        self.selected_row = None
        self.load_all_products()
    
    def closeEvent(self, event):
        """프로그램 종료"""
        self.conn.close()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    manager = ProductManager()
    manager.show()
    sys.exit(app.exec_())