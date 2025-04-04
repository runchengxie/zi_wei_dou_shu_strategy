import datetime
import tushare as ts
import pandas as pd
import matplotlib.pyplot as plt
import os

##########################
# 1) 定义飞星四化规则
##########################
def get_tiangan(year):
    """
    简化获取一个年份对应的天干。实际紫微斗数要根据农历干支来算，
    这里仅做演示，假设: year % 10 来映射到甲乙丙丁戊己庚辛壬癸
    """
    tiangan_list = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
    return tiangan_list[year % 10]

def get_four_transformations(birth_tiangan):
    """
    根据“出生年干”，返回主要星曜的化禄、化权、化科、化忌信息。
    这里仅随意举例做一个简单表。
    真实紫微斗数的完整对照更复杂，此处是示例。
    
    返回格式可理解为:
    {
      "廉贞": "禄",
      "破军": "权",
      "武曲": "科",
      "太阳": "忌",
      ...
    }
    """
    # 示例：假设“甲年”的四化星表
    # 这里只举四颗星，你可以自行扩展
    four_transform_dict = {
        "甲": {
            "廉贞": "禄",
            "破军": "权",
            "武曲": "科",
            "太阳": "忌"
        },
        "乙": {
            "紫微": "禄",
            "天机": "权",
            "太阴": "科",
            "巨门": "忌"
        },
        "丙": {
            "天同": "禄",
            "廉贞": "权",
            "武曲": "科",
            "太阳": "忌"
        },
        # ...省略其他年干，仅做示例
    }
    return four_transform_dict.get(birth_tiangan, {})

##########################
# 2) 定义财帛宫的主星 (示例)
##########################
def get_finance_star(birth_tiangan):
    """
    假设财帛宫主星是固定的，比如“武曲”，或者根据出生年干简单映射。
    这里可根据你的实际命盘来设定。
    """
    # 也可以写复杂一些，比如不同年干财帛宫主星不一样
    if birth_tiangan == "甲":
        return "武曲"
    elif birth_tiangan == "乙":
        return "太阴"
    elif birth_tiangan == "丙":
        return "廉贞"
    else:
        # 默认为武曲
        return "武曲"

##########################
# 3) 根据“紫微飞星 & 财帛宫” 修改买卖决策
##########################
def zi_wei_dou_shu_signal(trade_date, finance_star_trans):
    """
    将原先基于月份/日期的逻辑改为用“数值打分”+“星曜四化打分”综合判定。
    """
    month = trade_date.month
    day = trade_date.day

    # 基础评分：示例（原 buy=+2, sell=-2, hold=0）
    base_score = 0
    if month in [1, 4, 7, 10]:
        base_score = 2 if day % 2 == 0 else 0
    elif month in [2, 5, 8, 11]:
        base_score = -2 if day % 3 == 0 else 0

    # 星曜打分：禄=+2, 权=+1, 科=0, 忌=-2
    star_score = 0
    if finance_star_trans == "禄":
        star_score = 2
    elif finance_star_trans == "权":
        star_score = 1
    elif finance_star_trans == "忌":
        star_score = -2

    total_score = base_score + star_score

    # 根据阈值判定
    if total_score >= 2:
        return "buy"
    elif total_score <= -2:
        return "sell"
    else:
        return "hold"


def predict_buy_sell_zi_wei_stock(birth_year=1990):
    """
    主要函数：
    - 参数 birth_year：输入你或策略主体的出生年份，用于确定年干
    - 然后提取该年干下的财帛宫主星，以及该主星的四化结果
    - 最后在回测时根据“月/日” + “四化结果” 综合决定买卖
    """
    # 1) 获取年干
    tiangan = get_tiangan(birth_year)
    # 2) 获取该年干下的所有星曜四化信息
    transformations = get_four_transformations(tiangan)
    # 3) 获取财帛宫主星
    finance_star = get_finance_star(tiangan)
    # 4) 取得财帛宫主星在此年干下的"化"结果
    finance_star_trans = transformations.get(finance_star, None)  # 可能是 "禄" "权" "科" "忌" 或 None

    token = os.getenv("TUSHARE_API_KEY")
    if token:
        ts.set_token(token)
        pro = ts.pro_api()
        end_date = datetime.datetime.now().strftime("%Y%m%d")
        start_date = (datetime.datetime.now() - datetime.timedelta(days=365)).strftime("%Y%m%d")
        df = pro.daily(ts_code='600036.SH', start_date=start_date, end_date=end_date)
        df.sort_values('trade_date', inplace=True)
        df.reset_index(drop=True, inplace=True)
    else:
        # 如果没有 TuShare token，就用 akshare 做演示
        import akshare as ak
        df = ak.stock_zh_a_daily(symbol="sh600036", adjust="qfq")
        df.rename(columns={"date": "trade_date"}, inplace=True)
        df.sort_values("trade_date", inplace=True)
        df.reset_index(drop=True, inplace=True)
    
    # 将 trade_date 转换为 datetime
    df['trade_date'] = pd.to_datetime(df['trade_date'])

    # 基于修正后的 zi_wei_dou_shu_signal 生成交易信号
    signals = []
    for i in range(len(df)):
        date = df.loc[i, 'trade_date']
        signal = zi_wei_dou_shu_signal(date, finance_star_trans)
        signals.append(signal)
    df['signal'] = signals

    # 简单回测：初始资金 10000
    capital = 10000
    holding = False
    shares = 0
    for i in range(len(df)):
        if df.loc[i, 'signal'] == 'buy' and not holding:
            # 用开盘价买入
            shares = capital // df.loc[i, 'open']
            capital -= shares * df.loc[i, 'open']
            holding = True
        elif df.loc[i, 'signal'] == 'sell' and holding:
            # 用开盘价卖出
            capital += shares * df.loc[i, 'open']
            shares = 0
            holding = False

    # 如果最后还持有，就收盘时变现
    if holding:
        capital += shares * df.loc[len(df)-1, 'open']

    roi = (capital - 10000) / 10000 * 100

    # 画图
    plt.figure(figsize=(10,5))
    plt.plot(df['trade_date'], df['close'], label='Close Price')
    buy_points = df[df.signal == 'buy']
    sell_points = df[df.signal == 'sell']
    plt.scatter(buy_points['trade_date'], buy_points['close'], marker='^', color='g', label='Buy')
    plt.scatter(sell_points['trade_date'], sell_points['close'], marker='v', color='r', label='Sell')
    plt.legend()
    plt.title(f"600036 Stock ZiWei Strategy (BirthYear={birth_year}, ROI: {roi:.2f}%)")

    import matplotlib.dates as mdates
    ax = plt.gca()
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.gcf().autofmt_xdate()
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    # 你可以在这里修改 birth_year 来测试不同年干
    predict_buy_sell_zi_wei_stock(birth_year=1990)
