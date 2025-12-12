"""
네이버 금융 테마별 시세 크롤링
- 테마명, 전일대비, 최근3일 등락률, 등락현황, 주도주 정보를 수집
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime


def crawl_theme_page(page=1):
    """
    네이버 금융 테마별 시세 페이지 크롤링

    Args:
        page (int): 페이지 번호

    Returns:
        list: 테마 정보 딕셔너리 리스트
    """
    url = f'https://finance.naver.com/sise/theme.naver?&page={page}'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # 테마 테이블 찾기 - 여러 방법 시도
        table = soup.find('table', class_='type_1')

        if not table:
            # class가 없는 경우도 시도
            tables = soup.find_all('table')
            for t in tables:
                if 'type_1' in str(t.get('class', [])) or 'theme' in str(t.get('class', [])):
                    table = t
                    break

        if not table:
            print(f"페이지 {page}에서 테이블을 찾을 수 없습니다.")
            return []

        themes = []
        # tbody 태그가 없을 수도 있으므로 직접 tr 찾기
        rows = table.find_all('tr')

        for row in rows:
            # 빈 행이나 구분선 행 건너뛰기
            if 'blank' in row.get('class', []) or 'division_line' in row.get('class', []):
                continue

            cols = row.find_all('td')

            # 데이터가 있는 행만 처리
            if len(cols) >= 8:
                try:
                    # 테마명과 테마 번호 추출
                    theme_link = cols[0].find('a')
                    theme_name = theme_link.text.strip() if theme_link else ''
                    theme_url = theme_link.get('href', '') if theme_link else ''

                    # 테마 번호 추출 (예: /sise/sise_group_detail.naver?type=theme&no=543)
                    theme_no = ''
                    if 'no=' in theme_url:
                        theme_no = theme_url.split('no=')[1].split('&')[0]

                    # 전일대비 등락률
                    change_rate = cols[1].text.strip().replace('\n', '').replace('\t', '')

                    # 최근 3일 등락률
                    recent_3days = cols[2].text.strip().replace('\n', '').replace('\t', '')

                    # 등락현황
                    up_count = cols[3].text.strip()
                    same_count = cols[4].text.strip()
                    down_count = cols[5].text.strip()

                    # 주도주 1, 2
                    leader1_link = cols[6].find('a')
                    leader1_name = leader1_link.text.strip() if leader1_link else ''
                    leader1_code = ''
                    if leader1_link and 'code=' in leader1_link.get('href', ''):
                        leader1_code = leader1_link.get('href').split('code=')[1].split('&')[0]

                    leader2_link = cols[7].find('a')
                    leader2_name = leader2_link.text.strip() if leader2_link else ''
                    leader2_code = ''
                    if leader2_link and 'code=' in leader2_link.get('href', ''):
                        leader2_code = leader2_link.get('href').split('code=')[1].split('&')[0]

                    theme_data = {
                        '테마번호': theme_no,
                        '테마명': theme_name,
                        '전일대비': change_rate,
                        '최근3일등락률': recent_3days,
                        '상승': up_count,
                        '보합': same_count,
                        '하락': down_count,
                        '주도주1': leader1_name,
                        '주도주1코드': leader1_code,
                        '주도주2': leader2_name,
                        '주도주2코드': leader2_code,
                        '페이지': page
                    }

                    themes.append(theme_data)

                except Exception as e:
                    print(f"행 파싱 중 오류: {e}")
                    continue

        return themes

    except Exception as e:
        print(f"페이지 {page} 크롤링 중 오류: {e}")
        return []


def crawl_all_themes(max_pages=7):
    """
    모든 테마 페이지 크롤링

    Args:
        max_pages (int): 크롤링할 최대 페이지 수 (기본값: 7)

    Returns:
        DataFrame: 모든 테마 정보가 담긴 데이터프레임
    """
    all_themes = []

    for page in range(1, max_pages + 1):
        print(f"{page}/{max_pages} 페이지 크롤링 중...")
        themes = crawl_theme_page(page)
        all_themes.extend(themes)

        # 서버 부하 방지를 위한 대기
        if page < max_pages:
            time.sleep(1)

    df = pd.DataFrame(all_themes)
    print(f"\n총 {len(df)}개의 테마 정보를 수집했습니다.")

    return df


def save_to_csv(df, filename=None):
    """
    데이터프레임을 CSV 파일로 저장

    Args:
        df (DataFrame): 저장할 데이터프레임
        filename (str): 파일명 (없으면 자동 생성)
    """
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'naver_themes_{timestamp}.csv'

    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"\n파일 저장 완료: {filename}")


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("네이버 금융 테마별 시세 크롤링")
    print("=" * 60)

    # 모든 페이지 크롤링 (기본 7페이지)
    df = crawl_all_themes(max_pages=7)

    if not df.empty:
        # 결과 미리보기
        print("\n[상위 5개 테마]")
        print(df.head())

        # CSV 파일로 저장
        save_to_csv(df)

        # 기본 통계
        print("\n[기본 통계]")
        print(f"총 테마 수: {len(df)}")
        print(f"평균 상승 종목 수: {df['상승'].astype(int).mean():.1f}")
        print(f"평균 하락 종목 수: {df['하락'].astype(int).mean():.1f}")
    else:
        print("\n크롤링된 데이터가 없습니다.")


if __name__ == "__main__":
    main()
