"""
통합 테스트 - 네이버 테마 크롤링 기능이 제대로 통합되었는지 확인
"""

import sys
sys.path.insert(0, 'c:/Work')

# stock_analyzer2 모듈에서 필요한 함수들을 import
try:
    from stock_analyzer2 import (
        crawl_theme_page,
        crawl_all_themes,
        format_theme_results,
        handle_theme_crawling
    )
    print("✅ 모든 함수 import 성공!")
    print("✅ 네이버 테마 크롤링 기능이 stock_analyzer2.py에 통합되었습니다.")
    print("\n사용 가능한 함수:")
    print("  - crawl_theme_page(page)")
    print("  - crawl_all_themes(max_pages)")
    print("  - format_theme_results(df, top_n)")
    print("  - handle_theme_crawling()")
    print("\n메뉴에서 '1번'을 선택하면 테마 크롤링이 실행됩니다.")

except ImportError as e:
    print(f"❌ Import 실패: {e}")
    sys.exit(1)
