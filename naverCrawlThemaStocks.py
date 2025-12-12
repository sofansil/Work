"""
네이버 금융 테마별 종목 상세 정보 크롤링
- 특정 테마에 속한 종목들의 상세 정보 수집
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime


def crawl_theme_stocks(theme_no, theme_name=""):
    """
    특정 테마에 속한 종목들의 상세 정보 크롤링

    Args:
        theme_no (str): 테마 번호
        theme_name (str): 테마명 (선택사항)

    Returns:
        list: 종목 정보 딕셔너리 리스트
    """
    url = f'https://finance.naver.com/sise/sise_group_detail.naver?type=theme&no={theme_no}'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # 종목 테이블 찾기
        table = soup.find('table', class_='type_5')

        if not table:
            print(f"테마 {theme_no}에서 테이블을 찾을 수 없습니다.")
            return []

        stocks = []
        tbody = table.find('tbody')
        if not tbody:
            print(f"테마 {theme_no}에서 tbody를 찾을 수 없습니다.")
            return []

        rows = tbody.find_all('tr')

        for row in rows:
            # 빈 행 건너뛰기
            if row.get('class') and 'blank' in ' '.join(row.get('class', [])):
                continue

            cols = row.find_all('td')

            # 데이터가 있는 행만 처리 (최소 10개 컬럼)
            if len(cols) >= 10:
                try:
                    # 종목명과 종목코드 추출
                    name_col = cols[0]
                    stock_link = name_col.find('a')
                    stock_name = stock_link.text.strip() if stock_link else ''
                    stock_code = ''
                    if stock_link and 'code=' in stock_link.get('href', ''):
                        stock_code = stock_link.get('href').split('code=')[1].split('&')[0]

                    # 편입 사유 추출
                    info_text = ''
                    info_layer = cols[1].find('div', class_='info_layer_wrap')
                    if info_layer:
                        info_p = info_layer.find('p', class_='info_txt')
                        if info_p:
                            info_text = info_p.text.strip()

                    # 현재가
                    current_price = cols[2].text.strip().replace(',', '')

                    # 전일비
                    change = cols[3].text.strip().replace('\n', '').replace('\t', '').replace(',', '')

                    # 등락률
                    change_rate = cols[4].text.strip().replace('\n', '').replace('\t', '')

                    # 매수호가
                    buy_price = cols[5].text.strip().replace(',', '')

                    # 매도호가
                    sell_price = cols[6].text.strip().replace(',', '')

                    # 거래량
                    volume = cols[7].text.strip().replace(',', '')

                    # 거래대금
                    amount = cols[8].text.strip().replace(',', '')

                    # 전일거래량
                    prev_volume = cols[9].text.strip().replace(',', '')

                    stock_data = {
                        '테마번호': theme_no,
                        '테마명': theme_name,
                        '종목코드': stock_code,
                        '종목명': stock_name,
                        '현재가': current_price,
                        '전일비': change,
                        '등락률': change_rate,
                        '매수호가': buy_price,
                        '매도호가': sell_price,
                        '거래량': volume,
                        '거래대금': amount,
                        '전일거래량': prev_volume,
                        '편입사유': info_text
                    }

                    stocks.append(stock_data)

                except Exception as e:
                    print(f"행 파싱 중 오류: {e}")
                    continue

        return stocks

    except Exception as e:
        print(f"테마 {theme_no} 크롤링 중 오류: {e}")
        return []


def crawl_multiple_themes(theme_list):
    """
    여러 테마의 종목 정보를 한번에 크롤링

    Args:
        theme_list (list): [(테마번호, 테마명), ...] 형태의 리스트

    Returns:
        DataFrame: 모든 종목 정보가 담긴 데이터프레임
    """
    all_stocks = []

    for i, (theme_no, theme_name) in enumerate(theme_list, 1):
        print(f"{i}/{len(theme_list)} {theme_name}(#{theme_no}) 크롤링 중...")
        stocks = crawl_theme_stocks(theme_no, theme_name)
        all_stocks.extend(stocks)

        # 서버 부하 방지를 위한 대기
        if i < len(theme_list):
            time.sleep(1)

    df = pd.DataFrame(all_stocks)
    print(f"\n총 {len(df)}개의 종목 정보를 수집했습니다.")

    return df


def crawl_all_themes_from_csv(csv_file):
    """
    이전에 수집한 테마 리스트 CSV 파일을 읽어서 모든 테마의 종목 정보 크롤링

    Args:
        csv_file (str): 테마 리스트 CSV 파일 경로

    Returns:
        DataFrame: 모든 종목 정보가 담긴 데이터프레임
    """
    try:
        # 테마 리스트 읽기
        themes_df = pd.read_csv(csv_file, encoding='utf-8-sig')
        print(f"총 {len(themes_df)}개의 테마를 읽었습니다.")

        # 상위 N개 테마만 크롤링 (전체 크롤링 시 시간이 오래 걸림)
        max_themes = 10  # 필요시 변경
        themes_df = themes_df.head(max_themes)

        theme_list = list(zip(themes_df['테마번호'], themes_df['테마명']))

        return crawl_multiple_themes(theme_list)

    except Exception as e:
        print(f"CSV 파일 읽기 오류: {e}")
        return pd.DataFrame()


def save_to_csv(df, filename=None):
    """
    데이터프레임을 CSV 파일로 저장

    Args:
        df (DataFrame): 저장할 데이터프레임
        filename (str): 파일명 (없으면 자동 생성)
    """
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'naver_theme_stocks_{timestamp}.csv'

    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"\n파일 저장 완료: {filename}")


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("네이버 금융 테마별 종목 상세 정보 크롤링")
    print("=" * 60)

    # 방법 1: 특정 테마 몇 개만 크롤링
    theme_list = [
        ('543', '의료AI'),
        ('98', '음원/음반'),
        ('576', '퓨리오사AI'),
        ('155', '반도체 대표주(생산)'),
        ('112', '공기청정기')
    ]

    df = crawl_multiple_themes(theme_list)

    # 방법 2: 이전에 수집한 테마 리스트에서 읽어오기
    # df = crawl_all_themes_from_csv('naver_themes_20251210_215449.csv')

    if not df.empty:
        # 결과 미리보기
        print("\n[상위 5개 종목]")
        print(df[['테마명', '종목명', '현재가', '등락률', '거래량']].head())

        # CSV 파일로 저장
        save_to_csv(df)

        # 기본 통계
        print("\n[기본 통계]")
        print(f"총 종목 수: {len(df)}")
        print(f"테마 수: {df['테마명'].nunique()}")
        print(f"평균 등락률: {df['등락률'].str.replace('%', '').str.replace('+', '').astype(float).mean():.2f}%")
    else:
        print("\n크롤링된 데이터가 없습니다.")


if __name__ == "__main__":
    main()
