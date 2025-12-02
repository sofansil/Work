# 파일에 쓰기와 읽기 연습.py

# demo.txt 파일에 쓰기: write text mode
# 파일 인스턴스가 리턴. 유니코드 작업을 위해 endcoding='utf-8' 지정
f = open('demo.txt', 'wt', encoding='utf-8')
f.write('안녕하세요!\n')
f.write('파이썬 파일 입기, 쓰기 연습입니다.\n')
f.write('세번쨰 라인\n')
f.close()

# demo.txt 파일에서 읽기: read text mode
f = open('demo.txt', 'rt', encoding='utf-8')
# 파일의 끝까지 읽기를 해서 문자열 변수로 리턴
content = f.read()
print(content)
f.close()

