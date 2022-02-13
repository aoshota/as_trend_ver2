from urllib import response
import numpy as np
import requests
import time
import json
from discordwebhook import Discord
import re

# 仕様
# ±σ1を3回連続で超えたらエントリー（指値注文）
# ±σ1を1回超えたら決済（指値注文）
# SMA20を超えたら損切り（成行注文）
# 指値注文は板情報から金額を設定する
# ローソク足は10分足を使用

# 定数
# APIキーなどの不変な変数をcontentに格納
# content=["lineToken":"","apiKey","","secretKey":"","discordUrl":"","endPointPublic":"","pathGetRate":""]
pathContent = "content.json"
with open(pathContent) as f:
  content = json.load(f)
discord = Discord(url=content["discordUrl"]) # discordインスタンスを作成

# パラメータ
candle_stick_time = 1 # ローソク足の時間(分)

# 最新のレートをAPIで取得する関数
# レスポンスがjsonではないとき、0を返す
# {'ask':'', 'bid':'', 'high':'', 'last':'', 'low':'', 'symbol':'', 'timestamp':'', 'volume':''}
def GetRate():
	while True:
		try:
			response = requests.get(content["endPointPublic"] + content["pathGetRate"])
			if "json" in response.headers.get("content-type"):
				data = response.json()["data"][0]
				data["timestamp"] = data["timestamp"].replace("T"," ")[:-5] # timestampをYYYY-MM-DD HH:MM:SSに整形
				return data # レートのJSONデータを返す
			else:
				return 0
		except requests.exceptions.RequestException as e:
			print("最新の価格取得でエラー発生 : ",e)
			print("1秒待機してやり直します")
			time.sleep(1)

# 指定した時間(分)ぴったりの時にTrueを返す関数
# timestamp=HH:MM:SS(str)
def JustTime(timestamp,set_minute):
  flag_just_time = False
  timestamp_minute = int(re.findall(":(.*):",timestamp)[0]) # timestampから分だけ抽出
  timestamp_sec = int(timestamp[-2:]) # timestampから秒だけ抽出
  if timestamp_sec >= 59 or timestamp_sec <= 1: # APIで0秒ぴったりのデータを取りこぼすことがあるため幅を持たせる
    flag_just_time = True
    if ((timestamp_minute % set_minute == (set_minute - 1)) and timestamp_sec >= 59) or ((timestamp_minute % set_minute == 0) and timestamp_sec <= 1 ) :
      return flag_just_time
    else:
      return False
  return flag_just_time

# BBを計算する関数
# data = [終値, ..., 終値]（20個の終値のデータ）
# bband = {"mean":,"upper":,"lower":}
def CalcBB(data):
	bband = {}
	bband["mean"] = sum(data) / len(data)
	bband["upper"] = bband["mean"] + np.std(data) * 1
	bband["lower"] = bband["mean"] + np.std(data) * (-1)
	return bband

# 現在のBBを計算する関数
def GetBB(flag_just_time,element):
  if flag_just_time: # 指定した時間のデータの時
    if len(element["data_bb_20"]) < 19: # 最初の19個が揃うまでの処理
      element["data_bb_20"].append(int(data_now["last"]))
    else:
      element["data_bb_20"].append(int(data_now["last"])) # 20個目のデータを追加
      element["data_bb"] = CalcBB(element["data_bb_20"]) # BBを計算
      print(data_now["timestamp"],end=" ")
      print(element["data_bb_20"])
      element["data_bb_20"] = element["data_bb_20"][1:] # 1番古いデータを削除
    element["flag_bb_20"] = 1 # 指定時間のデータが取得できたら1(59~1の幅でデータを取るのを終了)
  else:
    element["flag_bb_20"] = 0 # 指定時間のデータを取得できていないので59~1の幅でデータを取る
  return element

element = {
	"data_bb_20" : [], # BBで使う20個のデータを格納する配列
	"data_bb" : {}, # 現在のBB（偏差、移動平均）
	"flag_minus" : 0, # レートがσを連続で下回った回数
	"flag_plus" : 0, # レートがσを連続で上回った回数
	"flag_position" : "NO", # 現在のポジション(NO:ポジションなし、BUY:ロング、SELL:ショート)
	"flag_bb_20" : 0 # 指定時間のデータが取得できたら1、取得できていないときは0
}

while True:
  data_now = GetRate() # レートのJSONデータ
  if data_now == 0: # APIでJSONが返ってこないときは最初の処理に戻る
    continue
  timestamp = data_now["timestamp"][-8:] #　最新レートのタイムスタンプを整形(HH:MM:SS)
  flag_just_time = JustTime(timestamp,candle_stick_time) # 指定のローソク足の時間の時True

	# BBのデータ集めとBBの計算
  element = GetBB(flag_just_time,element)

  # 注文処理

  # 注文処理や決済処理が終わったらsleep(5)を入れる
  if element["flag_bb_20"] : time.sleep(5) # 59~01秒のデータ幅があるため、どれか1つ取得できたら他のデータを取得しないように5秒遅延させる

  time.sleep(1)
