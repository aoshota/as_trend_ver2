from urllib import response
import numpy as np
import requests
import time
import json
from discordwebhook import Discord
import re

# 仕様
# ±σ1を3回連続で超えたらエントリー（指値注文）
# sma5を1回超えたら決済（指値注文）
# SMA20を超えたら損切り（成行注文）
# 指値注文は板情報から金額を設定する
# ローソク足は10分足を使用

# 定数
# APIキーなどの定数をcontentに格納
# content=["lineToken":"","apiKey","","secretKey":"","discordUrl":"","endPointPublic":"","pathGetRate":""]
pathContent = "content.json"
with open(pathContent) as f:
  content = json.load(f)
discord = Discord(url=content["discordUrl"]) # discordインスタンスを作成

# パラメータ
candle_stick_time = 10 # ローソク足の時間(分)

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
# 10分を指定したら、例えば、11:59 ~ 12:01の時にTrueを返す
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
def GetBB(data_now,flag_just_time,element):
  if flag_just_time: # 指定した時間のデータの時
    # with open("kline.csv", mode="a") as f:
    #   print(data_now,file=f)
    if len(element["data_bb_20"]) < 19: # 最初の19個が揃うまでの処理
      element["data_bb_20"].append(int(data_now["last"]))
    else: # データが19個あったら、20個目を追加してBBを計算
      element["data_bb_20"].append(int(data_now["last"])) # 20個目のデータを追加
      element["data_bb"] = CalcBB(element["data_bb_20"]) # BBを計算
      print(data_now)
      print(element)
      with open("data_now.csv",mode="a") as f:
        print(data_now,file=f)
      with open("element.csv",mode="a") as f:
        print(element,file=f)
      element["data_bb_20"] = element["data_bb_20"][1:] # 1番古いデータを削除
    element["flag_bb_20"] = 1 # 指定時間のデータが取得できたら1(59~1の幅でデータを取るのを終了)
  else:
    element["flag_bb_20"] = 0 # 指定時間のデータを取得できていないので59~1の幅でデータを取る
  return element

# エントリー処理
def Entry(data_now,element):
  if element["flag_position"] == "BUY":
    print("ロングで注文")
    print("買:" + data_now["ask"])
    print("money:",element["demo"]["money"])
    discord.post(content="ロングで注文")
    discord.post(content="買:" + data_now["ask"])
    discord.post(content="money:" + str(element["demo"]["money"]))
    element["demo"]["money_tmp"] = int(data_now["ask"])
  if element["flag_position"] == "SELL":
    print("ショートで注文")
    print("売:" + data_now["bid"])
    print("money:",element["demo"]["money"])
    discord.post(content="ショートで注文")
    discord.post(content="売:" + data_now["bid"])
    discord.post(content="money:" + str(element["demo"]["money"]))
    element["demo"]["money_tmp"] = int(data_now["bid"])
  return element

# 決済の処理
def Settlement(data_now,element):
  if element["flag_position"] == "BUY":
    element["demo"]["money"] += (int(data_now["bid"]) - element["demo"]["money_tmp"])
    print("ロングの決済")
    print("売:",data_now["bid"])
    print("money:",element["demo"]["money"])
    discord.post(content="ロングの決済")
    discord.post(content="売:" + data_now["bid"])
    discord.post(content="money:" + str(element["demo"]["money"]))
  if element["flag_position"] == "SELL":
    element["demo"]["money"] += (element["demo"]["money_tmp"] - int(data_now["ask"]))
    print("ショートの決済")
    print("買:",data_now["ask"])
    print("money:",element["demo"]["money"])
    discord.post(content="ショートの決済")
    discord.post(content="買:" + data_now["ask"])
    discord.post(content="money:" + str(element["demo"]["money"]))
  return element

# 損切りの処理(成行注文)
# 決済注文が通らなかったときは成行で損切りする
def StopLoss(element):
  if element["flag_position"] == "BUY":
    print("売りで決済")
  if element["flag_position"] == "SELL":
    print("買いで決済")
  return element

# エントリー条件を検査してエントリーする関数
def CheckAndEntry(data_now,element):
  # 現在のレートが+σ1より大きい時、element["flag_plus"]に1を足す
  if int(data_now["last"]) >= element["data_bb"]["upper"]:
    element["flag_plus"] += 1
  else:
    element["flag_plus"] = 0
  # 現在のレートが-σ1より小さい時、element["flag_minus"]に1を足す
  if int(data_now["last"]) <= element["data_bb"]["lower"]:
    element["flag_minus"] += 1
  else:
    element["flag_minus"] = 0
  # 直近3回のレートがσ1より大きい時、ロングでエントリーする
  if element["flag_plus"] == 3:
    element["flag_position"] = "BUY"
    element = Entry(data_now,element)
    element["flag_plus"] = 0
  # 直近3回のレートが-σ1より小さい時、ショートでエントリーする
  if element["flag_minus"] == 3:
    element["flag_position"] = "SELL"
    element = Entry(data_now,element)
    element["flag_minus"] = 0

  return element


# 決済条件を検査して決済する関数
def CheckAndSettlement(data_now,element):
  # ロングポジションを入れている時、現在のレートがsma5より小さかったら決済、移動平均(SMA20)より小さかったら損切り(成行注文)
  if element["flag_position"] == "BUY":
    if int(data_now["last"]) <= element["sma5"]:
      element = Settlement(data_now,element)
      element["flag_position"] = "NO"
    if int(data_now["last"]) <= element["data_bb"]["mean"]:
      element = StopLoss(element)
      element["flag_position"] = "NO"
  # ショートポジションを入れている時、現在のレートがsma5より大きかったら決済、移動平均(SMA20)より大きかったら損切り(成行注文)
  elif element["flag_position"] == "SELL":
    if int(data_now["last"]) >= element["sma5"]:
      element = Settlement(data_now,element)
      element["flag_position"] = "NO"
    if int(data_now["last"]) >= element["data_bb"]["mean"]:
      element = StopLoss(element)
      element["flag_position"] = "NO"

  return element


element = {
	"data_bb_20" : [], # BBで使う20個のデータを格納する配列
	"data_bb" : {}, # 現在のBB（偏差、移動平均）
	"flag_minus" : 0, # レートがσを連続で下回った回数
	"flag_plus" : 0, # レートがσを連続で上回った回数
	"flag_position" : "NO", # 現在のポジション(NO:ポジションなし、BUY:ロング、SELL:ショート)
	"flag_bb_20" : 0, # 指定時間のデータが取得できたら1、取得できていないときは0
  "sma5" : 0,
  "demo" : {"money" : 0, "money_tmp" : 0} # デモ用の所持金を計算するための変数
}

while True:
  data_now = GetRate() # 現在のレートのJSONデータ
  if data_now == 0: # APIでJSONが返ってこないときは最初の処理に戻る
    continue
  timestamp = data_now["timestamp"][-8:] #　最新レートのタイムスタンプを整形(HH:MM:SS)
  flag_just_time = JustTime(timestamp,candle_stick_time) # 指定のローソク足の時間の時True

	# BBのデータ集めとBBの計算の後にエントリー・決済処理
  element = GetBB(data_now,flag_just_time,element)

  if element["data_bb"] and element["flag_bb_20"]: # BBのデータがあったらエントリー・決済条件を検査する
    if element["flag_position"] == "NO": # flag_positionがNOのときはエントリー条件検査とエントリー処理
      element = CheckAndEntry(data_now,element)
    else:# flag_positionがBUY・SELLのときは決済条件検査と決済処理
      element["sma5"] = CalcBB(element["data_bb_20"][15:])["mean"] # 決済で使うsma5を代入
      element = CheckAndSettlement(data_now,element)

  # 59~01秒のデータ幅があるため、どれか1つ取得できたら他のデータを取得しないように5秒遅延させる
  if element["flag_bb_20"] : time.sleep(5)

  time.sleep(1)
