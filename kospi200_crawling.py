import requests
from bs4 import BeautifulSoup
import pandas as pd

def crawl_kospi200():
    url = "https://finance.naver.com/sise/entryJongmok.naver?type=KPI200"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    response = requests.get(url, headers=headers)
    response.encoding = 'utf-8'
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # 편입종목 테이블 찾기 (class="type_1")
    table = soup.find('table', {'class': 'type_1'})
    
    data = []
    if table:
        rows = table.find_all('tr')[2:]  # 헤더 2줄 제외
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 7:
                try:
                    company = cols[0].text.strip()
                    price = cols[1].text.strip()
                    
                    # 전일비는 span에서 추출
                    change = cols[2].find('span', {'class': 'tah'})
                    change_text = change.text.strip() if change else "0"
                    
                    change_rate = cols[3].text.strip()
                    volume = cols[4].text.strip()
                    amount = cols[5].text.strip()
                    market_cap = cols[6].text.strip()
                    
                    data.append({
                        '종목명': company,
                        '현재가': price,
                        '전일비': change_text,
                        '등락률': change_rate,
                        '거래량': volume,
                        '거래대금(백만)': amount,
                        '시가총액(억)': market_cap
                    })
                except Exception as e:
                    print(f"오류 발생: {e}")
                    continue
    
    df = pd.DataFrame(data)
    
    # 데이터프레임 포맷팅
    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_rows', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', 20)
    
    print("\n" + "="*150)
    print("코스피200 편입종목 상위".center(150))
    print("="*150)
    
    # 각 컬럼 정렬을 위한 포맷팅
    for idx, row in df.iterrows():
        print(f"{idx+1:3} | {row['종목명']:15} | {row['현재가']:>10} | {row['전일비']:>8} | {row['등락률']:>8} | {row['거래량']:>12} | {row['거래대금(백만)']:>12} | {row['시가총액(억)']:>12}")
    
    print("="*150)
    print(f"\n총 {len(df)}개 종목\n")
    
    # CSV 파일로 저장
    df.to_csv('kospi200.csv', index=False, encoding='utf-8-sig')
    print("✓ kospi200.csv 파일로 저장되었습니다.\n")
    
    return df

if __name__ == "__main__":
    crawl_kospi200()