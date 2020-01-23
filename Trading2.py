#!/usr/bin/env python
# coding: utf-8

# In[1]:


import numpy as np
import pandas as pd
from alpha_vantage.timeseries import TimeSeries
import copy
pd.core.common.is_list_like = pd.api.types.is_list_like
import pandas_datareader.data as pdr
import datetime as dt
import yfinance as yf
import requests
import time
from bs4 import BeautifulSoup as bs
import matplotlib.pyplot as plt


# In[2]:


def ATR(DF,n):
    "function to calculate True Range and Average True Range"
    df = DF.copy()
    df['H-L']=abs(df['High']-df['Low'])
    df['H-PC']=abs(df['High']-df['Adj Close'].shift(1))
    df['L-PC']=abs(df['Low']-df['Adj Close'].shift(1))
    df['TR']=df[['H-L','H-PC','L-PC']].max(axis=1,skipna=False)
    df['ATR'] = df['TR'].rolling(n).mean()
    #df['ATR'] = df['TR'].ewm(span=n,adjust=False,min_periods=n).mean()
    df2 = df.drop(['H-L','H-PC','L-PC'],axis=1)
    return df2['ATR']


# In[3]:


def CAGR(DF):
    "function to calculate the Cumulative Annual Growth Rate of a trading strategy"
    df = DF.copy()
    df["cum_return"] = (1 + df["ret"]).cumprod()
    n = len(df)/(252*78)
    CAGR = (df["cum_return"].tolist()[-1])**(1/n) - 1
    return CAGR


# In[4]:


def volatility(DF):
    "function to calculate annualized volatility of a trading strategy"
    df = DF.copy()
    vol = df["ret"].std() * np.sqrt(252*78)
    return vol


# In[5]:


def sharpe(DF,rf):
    "function to calculate sharpe ratio ; rf is the risk free rate"
    df = DF.copy()
    sr = (CAGR(df) - rf)/volatility(df)
    return sr
    


# In[6]:


def max_dd(DF):
    "function to calculate max drawdown"
    df = DF.copy()
    df["cum_return"] = (1 + df["ret"]).cumprod()
    df["cum_roll_max"] = df["cum_return"].cummax()
    df["drawdown"] = df["cum_roll_max"] - df["cum_return"]
    df["drawdown_pct"] = df["drawdown"]/df["cum_roll_max"]
    max_dd = df["drawdown_pct"].max()
    return max_dd


# In[14]:


tickers = ["MSFT","AAPL","FB","AMZN","INTC", "CSCO","VZ","IBM","QCOM","LYFT"]

ohlc_intraday = {}


# In[8]:


key = "A4AQMVBJVJNFIKVR"
ts = TimeSeries(key=key, output_format='pandas')


# In[15]:


attempt = 0 # initializing passthrough variable
drop = [] # initializing list to store tickers whose close price was successfully extracted
k=0
while len(tickers) != 0 and attempt <=6:
    tickers = [j for j in tickers if j not in drop]
    for i in range(len(tickers)):
        print(i)
        try:
            #can't access to alphavantage for more than 5 times a minute so we need to put the program to sleep 
            if k==5:
                time.sleep(60)
                k=0
                
            ohlc_intraday[tickers[i]] = ts.get_intraday(symbol=tickers[i],interval='5min', outputsize='full')[0]
            ohlc_intraday[tickers[i]].columns = ["Open","High","Low","Adj Close","Volume"]
            drop.append(tickers[i])  
            print(tickers[i])
            k += 1
        except:
            print(tickers[i]," :failed to fetch data...retrying")
            continue

    attempt+=1

 
tickers = ohlc_intraday.keys()


# In[16]:


print(ohlc_intraday.keys())


# In[42]:


tickers_signal = {}
tickers_ret = {}
for ticker in tickers:
    ohlc_intraday[ticker]["ATR"] = ATR(ohlc_intraday[ticker], 20)
    ohlc_intraday[ticker]["roll_max_cp"] = ohlc_intraday[ticker]["High"].rolling(20).max()
    ohlc_intraday[ticker]["roll_min_cp"] = ohlc_intraday[ticker]["Low"].rolling(20).min()
    ohlc_intraday[ticker]["roll_max_vol"] = ohlc_intraday[ticker]["Volume"].rolling(20).max()
    ohlc_intraday[ticker].dropna(inplace=True)
    tickers_signal[ticker] = ""
    tickers_ret[ticker] = []


# In[43]:


for ticker in tickers:
    print(ticker)
    for i in range(len(ohlc_intraday[ticker])):
        if tickers_signal[ticker] == "":
            tickers_ret[ticker].append(0)
            if ohlc_intraday[ticker]["High"][i] >= ohlc_intraday[ticker]["roll_max_cp"][i] and ohlc_intraday[ticker]["Volume"][i] > 1.5 * ohlc_intraday[ticker]["roll_max_vol"][i-1]:
                tickers_signal[ticker] = "Buy"
            elif ohlc_intraday[ticker]["Low"][i] <= ohlc_intraday[ticker]["roll_min_cp"][i] and ohlc_intraday[ticker]["Volume"][i] > 1.5 * ohlc_intraday[ticker]["roll_max_vol"][i-1]:
                tickers_signal[ticker] = "Sell"
            
        elif tickers_signal[ticker] == "Buy":
            if ohlc_intraday[ticker]["Adj Close"][i] < ohlc_intraday[ticker]["Adj Close"][i-1] - ohlc_intraday[ticker]["ATR"][i-1]:
                tickers_signal[ticker] == ""
                tickers_ret[ticker].append(((ohlc_intraday[ticker]["Adj Close"][i-1] - ohlc_intraday[ticker]["ATR"][i-1])/ohlc_intraday[ticker]["Adj Close"][i-1])-1)
            elif ohlc_intraday[ticker]["Low"][i] <= ohlc_intraday[ticker]["roll_min_cp"][i] and ohlc_intraday[ticker]["Volume"][i] > 1.5 * ohlc_intraday[ticker]["roll_max_vol"][i-1]:
                tickers_signal[ticker] = "Sell"
                tickers_ret[ticker].append(((ohlc_intraday[ticker]["Adj Close"][i-1] - ohlc_intraday[ticker]["ATR"][i-1])/ohlc_intraday[ticker]["Adj Close"][i-1])-1)
            else:
                tickers_ret[ticker].append((ohlc_intraday[ticker]["Adj Close"][i]/ohlc_intraday[ticker]["Adj Close"][i-1])-1)
            
        elif tickers_signal[ticker] == "Sell":
            if ohlc_intraday[ticker]["Adj Close"][i]>ohlc_intraday[ticker]["Adj Close"][i-1] + ohlc_intraday[ticker]["ATR"][i-1]:
                tickers_signal[ticker] = ""
                tickers_ret[ticker].append((ohlc_intraday[ticker]["Adj Close"][i-1]/(ohlc_intraday[ticker]["Adj Close"][i-1] + ohlc_intraday[ticker]["ATR"][i-1]))-1)
            elif ohlc_intraday[ticker]["High"][i]>=ohlc_intraday[ticker]["roll_max_cp"][i] and                ohlc_intraday[ticker]["Volume"][i]>1.5*ohlc_intraday[ticker]["roll_max_vol"][i-1]:
                tickers_signal[ticker] = "Buy"
                tickers_ret[ticker].append((ohlc_intraday[ticker]["Adj Close"][i-1]/(ohlc_intraday[ticker]["Adj Close"][i-1] + ohlc_intraday[ticker]["ATR"][i-1]))-1)
            else:
                tickers_ret[ticker].append((ohlc_intraday[ticker]["Adj Close"][i-1]/ohlc_intraday[ticker]["Adj Close"][i])-1)
                
    ohlc_intraday[ticker]["ret"] = np.array(tickers_ret[ticker])


# In[45]:


strategy_df = pd.DataFrame()
for ticker in tickers:
    strategy_df[ticker] = ohlc_intraday[ticker]["ret"]
strategy_df["ret"] = strategy_df.mean(axis=1)


# In[46]:


CAGR(strategy_df)


# In[47]:


sharpe(strategy_df,0.025)


# In[48]:


max_dd(strategy_df)  


# In[49]:


# vizualization of strategy return
(1+strategy_df["ret"]).cumprod().plot()


# In[ ]:




