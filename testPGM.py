import sys
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import QApplication
from pykiwoom.kiwoom import Kiwoom  # pip install pykiwoom

# VIDYA 계산 함수
def calculate_vidya(price, period=14):
    cmo = 100 * (price.diff().clip(lower=0).rolling(period).sum() - 
                 price.diff().clip(upper=0).abs().rolling(period).sum()) / \
          (price.diff().abs().rolling(period).sum())
    cmo = cmo.abs().fillna(0) / 100

    vidya = [price.iloc[0]]
    for i in range(1, len(price)):
        alpha = cmo.iloc[i]
        val = alpha * price.iloc[i] + (1 - alpha) * vidya[-1]
        vidya.append(val)
    return pd.Series(vidya, index=price.index)

# PyKiwoom 연동
app = QApplication(sys.argv)
kiwoom = Kiwoom()
kiwoom.CommConnect(block=True)

# 종목 코드 예: 삼성전자
code = "005930"
df = kiwoom.block_request("opt10081",
                          종목코드=code,
                          기준일자="20240417",
                          수정주가구분=1,
                          output="주식일봉차트조회",
                          next=0)

# 데이터 정리
df = pd.DataFrame(df)
df = df[['일자', '현재가']]
df['현재가'] = pd.to_numeric(df['현재가'])
df = df.sort_values('일자')
df.set_index('일자', inplace=True)

# VIDYA 계산
df['VIDYA'] = calculate_vidya(df['현재가'])

# 확인
print(df.tail())
