# coding:utf-8
from bs4 import BeautifulSoup
import urllib.request
# 정규표현식을 사용해서 검색
import re

f = open('todayhumor.txt', 'wt', encoding='utf-8')

#User-Agent를 조작하는 경우(아이폰에서 사용하는 사파리 브라우져의 헤더) 
hdr = {'User-agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3 like Mac OS X) AppleWebKit/603.1.23 (KHTML, like Gecko) Version/10.0 Mobile/14E5239e Safari/602.1'}

for n in range(1,11):
    #오늘의 유머 베스트 게시판 주소 
    data ='https://www.todayhumor.co.kr/board/list.php?table=bestofbest&page=' + str(n)
    print(data)
    
    #웹브라우져 헤더 추가 
    req = urllib.request.Request(data, headers = hdr)
    data = urllib.request.urlopen(req).read()
    page = data.decode('utf-8', 'ignore')
    soup = BeautifulSoup(page, 'html.parser')
    list = soup.find_all('td', attrs={"class":"subject"})

    for item in list:
        try:
            #<a> 태그를 검색
            title = item.find('a').text.strip()
            if re.search('미국', title):
                print(title)
                f.write(title + '\n')
        except:
                pass

f.close()


# <td class="subject">
# <a href="/board/view.php?table=bestofbest&amp;no=481391&amp=>공돌이 사고친썰
# </a><span class="list_memo_count_span"> [21]</span>  <span style="margin-left:4px;"><img src="//www.todayhumor.co.kr/board/images/list_icon_photo.gif" style="vertical-align:middle; margin-bottom:1px;"> </span><img src="//www.todayhumor.co.kr/board/images/list_icon_shovel.gif?2" alt="펌글" style="margin-right:3px;top:2px;position:relative"> </td>