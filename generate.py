import pandas as pd, numpy as np, yfinance as yf, plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import pandas_market_calendars as mcal
from html import escape
import os

root=Path('site'); root.mkdir(parents=True,exist_ok=True)
cache=Path('cache'); cache.mkdir(exist_ok=True)
groups={
'主要指数': [('SPY','S&P500'),('QQQ','NASDAQ100'),('DIA','NYダウ'),('IWM','小型株'),('RSP','均等加重'),('^SOX','半導体指数'),('TQQQ','NASDAQ100 3倍'),('ACWI','世界株式')],
'リスク指標': [('^VIX','VIX'),('^VXN','VXN'),('^VVIX','VVIX'),('^SKEW','SKEW'),('^TNX','米国10年金利'),('DX-Y.NYB','ドル指数'),('HYG','ハイイールド債'),('GLD','金'),('TLT','長期国債'),('USO','原油先物ETF')],
'基本11セクター':list(zip('XLK XLC XLY XLP XLF XLI XLE XLV XLU XLB XLRE'.split(),'情報技術 通信 一般消費財 生活必需品 金融 資本財・工業 エネルギー ヘルスケア 公益 素材 不動産'.split())),
'投資テーマ':list(zip('SMH IGV BOTZ QTUM URA NLR CIBR ITA XBI KRE ARKK'.split(),'半導体 ソフトウェア AI・ロボット 量子・先端技術 ウラン・原子力 原子力発電 サイバーセキュリティ 航空宇宙・防衛 バイオ 地方銀行 革新的成長企業'.split()))}
now=pd.Timestamp.now(tz='UTC'); cal=mcal.get_calendar('NYSE'); sched=cal.schedule(start_date=(now-pd.Timedelta(days=15)).date(),end_date=now.date()); target=sched.index[sched.market_close+pd.Timedelta(minutes=30)<=now][-1].normalize()
all_t=[t for g in groups.values() for t,n in g]; data={}; errors=[]
for i in range(0,len(all_t),5):
    batch=all_t[i:i+5]; print('取得:',batch)
    try:
        raw=yf.download(batch,period='2y',interval='1d',auto_adjust=True,group_by='ticker',threads=True,progress=False,timeout=10)
    except Exception as e:
        raw=pd.DataFrame(); print(e)
    for t in batch:
        p=cache/(t+'.csv')
        try:
            d=raw[t].copy() if isinstance(raw.columns,pd.MultiIndex) else raw.copy() if len(batch)==1 else pd.DataFrame()
            d=d.dropna(subset=['Close']); d.index=pd.to_datetime(d.index).tz_localize(None).normalize(); d=d.loc[d.index<=target].sort_index()
            if d.empty: raise ValueError('取得なし')
            if p.exists():
                old=pd.read_csv(p,index_col=0,parse_dates=True)
                if not old.empty and old.index.max()>d.index.max(): raise ValueError('取得データが古い')
            d.to_csv(p)
        except Exception as e:
            errors.append(t)
            try: d=pd.read_csv(p,index_col=0,parse_dates=True).loc[:target]
            except Exception: continue
        if not d.empty: data[t]=d
if not data or not any(d.index.max()==target for d in data.values()): raise RuntimeError('最新営業日のデータなし。既存サイトを維持します')
updated=now.tz_convert('Asia/Tokyo').strftime('%Y-%m-%d %H:%M')
parts=['<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{font-family:system-ui;margin:16px;background:#101722;color:#e5edf7}h2{color:#8ecaff}a{color:#8ecaff}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:7px;border-bottom:1px solid #455064;text-align:right}td:first-child{text-align:left}.scroll{overflow:auto}</style><h1>米国市場 日次チャート</h1>',f'<p>更新時刻（日本時間）: {updated} | 対象営業日: {target.date()} | 取得済み {len(data)}/{len(all_t)} | 取得失敗（キャッシュ使用含む）: {escape(", ".join(errors) or "なし")}</p><p>調整済日足・Yahoo Finance。市場によって取引日が異なります。古いデータは日付で確認してください。</p>']
parts.append(' ｜ '.join(f'<a href="#g{i}">{escape(g)}</a>' for i,g in enumerate(groups)))
for i,(g,items) in enumerate(groups.items()):
    parts.append(f'<h2 id="g{i}">{escape(g)}</h2><div class="scroll"><table><tr><th>銘柄</th><th>日付</th><th>終値</th><th>1日</th><th>5日</th><th>20日</th><th>60日</th></tr>')
    for t,n in items:
        if t not in data: parts.append(f'<tr><td>{t} {n}</td><td colspan="6">未取得</td></tr>'); continue
        d=data[t]; c=d.Close
        vals=[]
        for k in [1,5,20,60]:
            v=(c.iloc[-1]/c.iloc[-k-1]-1)*100 if len(c)>k and c.iloc[-k-1]!=0 else np.nan
            vals.append(f'<td style="color:{"#55d6a0" if v>=0 else "#ff8585"}">{v:+.2f}%</td>' if np.isfinite(v) else '<td>—</td>')
        parts.append(f'<tr><td>{t} {n}</td><td>{d.index[-1].date()}</td><td>{c.iloc[-1]:.2f}</td>'+''.join(vals)+'</tr>')
    parts.append('</table></div>')
    for j in range(0,len(items),3):
        row=items[j:j+3]; fig=make_subplots(rows=1,cols=len(row),subplot_titles=[f'{t} {n}' for t,n in row])
        for k,(t,n) in enumerate(row,1):
            if t not in data: continue
            d=data[t].copy(); c=d.Close
            for w in [20,50,200]: d[f'MA{w}']=c.rolling(w).mean()
            d=d.tail(120); x=d.index.strftime('%Y-%m-%d')
            if g=='リスク指標' and t.startswith('^'):
                fig.add_trace(go.Scatter(x=x,y=d.Close,name='終値',line=dict(color='#e5edf7'),showlegend=False),row=1,col=k)
            else:
                fig.add_trace(go.Candlestick(x=x,open=d.Open,high=d.High,low=d.Low,close=d.Close,showlegend=False),row=1,col=k)
            for w,color in [(20,'#e6b450'),(50,'#57b5e7'),(200,'#c792ea')]:
                fig.add_trace(go.Scatter(x=x,y=d[f'MA{w}'],name=f'MA{w}',line=dict(color=color,width=1),showlegend=False),row=1,col=k)
            fig.update_xaxes(type='category',nticks=5,rangeslider_visible=False,row=1,col=k)
        fig.update_layout(template='plotly_dark',height=340,margin=dict(l=35,r=20,t=45,b=35))
        parts.append(fig.to_html(full_html=False,include_plotlyjs='cdn' if i==0 and j==0 else False,config={'responsive':True}))
parts.append('<p>移動平均線：黄20日・青50日・紫200日。表示120営業日。騰落率は資金流出入額ではありません。</p></html>')
out=root/'index.html'; out.write_text('\n'.join(parts),encoding='utf-8')
(root/'.nojekyll').touch()
print('保存完了:',out)
