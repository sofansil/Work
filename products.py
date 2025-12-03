import sqlite3
import random
from typing import List, Tuple

class ProductDatabase:
    def __init__(self, db_name: str = r"c:\work\MyProduct.db"):
        self.db_name = db_name
        self.conn = None
        self.cursor = None
        self.init_database()
    
    def init_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS Products (
                productID INTEGER PRIMARY KEY AUTOINCREMENT,
                productName TEXT NOT NULL,
                productPrice INTEGER NOT NULL
            )
        ''')
        self.conn.commit()
    
    def insert(self, product_name: str, product_price: int) -> bool:
        """제품 추가"""
        try:
            self.cursor.execute('''
                INSERT INTO Products (productName, productPrice)
                VALUES (?, ?)
            ''', (product_name, product_price))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Insert 오류: {e}")
            return False
    
    def insert_many(self, products: List[Tuple[str, int]]) -> bool:
        """대량 제품 추가"""
        try:
            self.cursor.executemany('''
                INSERT INTO Products (productName, productPrice)
                VALUES (?, ?)
            ''', products)
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Bulk Insert 오류: {e}")
            return False
    
    def select_all(self) -> List[Tuple]:
        """모든 제품 조회"""
        self.cursor.execute('SELECT * FROM Products')
        return self.cursor.fetchall()
    
    def select_by_id(self, product_id: int) -> Tuple:
        """ID로 제품 조회"""
        self.cursor.execute('SELECT * FROM Products WHERE productID = ?', (product_id,))
        return self.cursor.fetchone()
    
    def select_by_price_range(self, min_price: int, max_price: int) -> List[Tuple]:
        """가격 범위로 제품 조회"""
        self.cursor.execute('''
            SELECT * FROM Products 
            WHERE productPrice BETWEEN ? AND ?
        ''', (min_price, max_price))
        return self.cursor.fetchall()
    
    def update(self, product_id: int, product_name: str = None, product_price: int = None) -> bool:
        """제품 수정"""
        try:
            if product_name and product_price:
                self.cursor.execute('''
                    UPDATE Products 
                    SET productName = ?, productPrice = ?
                    WHERE productID = ?
                ''', (product_name, product_price, product_id))
            elif product_name:
                self.cursor.execute('''
                    UPDATE Products 
                    SET productName = ?
                    WHERE productID = ?
                ''', (product_name, product_id))
            elif product_price:
                self.cursor.execute('''
                    UPDATE Products 
                    SET productPrice = ?
                    WHERE productID = ?
                ''', (product_price, product_id))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Update 오류: {e}")
            return False
    
    def delete(self, product_id: int) -> bool:
        """제품 삭제"""
        try:
            self.cursor.execute('DELETE FROM Products WHERE productID = ?', (product_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Delete 오류: {e}")
            return False
    
    def get_count(self) -> int:
        """전체 제품 개수"""
        self.cursor.execute('SELECT COUNT(*) FROM Products')
        return self.cursor.fetchone()[0]
    
    def close(self):
        """데이터베이스 연결 종료"""
        if self.conn:
            self.conn.close()


# 샘플 실행 코드
if __name__ == "__main__":
    db = ProductDatabase(r"c:\work\MyProduct.db")
    
    # 기존 데이터 삭제 (테스트용)
    db.cursor.execute('DELETE FROM Products')
    db.conn.commit()
    
    # 샘플 데이터 10만개 생성
    print("샘플 데이터 생성 중...")
    products = []
    product_names = ["노트북", "스마트폰", "태블릿", "모니터", "키보드", 
                     "마우스", "이어폰", "스피커", "카메라", "프린터"]
    
    for i in range(100000):
        name = random.choice(product_names) + f"_{i+1}"
        price = random.randint(10000, 1000000)
        products.append((name, price))
    
    db.insert_many(products)
    print(f"✓ 총 {db.get_count()}개의 제품이 저장되었습니다.\n")
    
    # SELECT 테스트
    print("--- SELECT 테스트 ---")
    print(f"ID 1번 제품: {db.select_by_id(1)}")
    print(f"가격 50000~100000 범위 제품 3개: {db.select_by_price_range(50000, 100000)[:3]}\n")
    
    # UPDATE 테스트
    print("--- UPDATE 테스트 ---")
    db.update(1, "프리미엄 노트북", 1500000)
    print(f"수정된 ID 1번 제품: {db.select_by_id(1)}\n")
    
    # DELETE 테스트
    print("--- DELETE 테스트 ---")
    before_count = db.get_count()
    db.delete(2)
    after_count = db.get_count()
    print(f"삭제 전: {before_count}개, 삭제 후: {after_count}개\n")
    
    db.close()
    print("✓ 작업 완료!")