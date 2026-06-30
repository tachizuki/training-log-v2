# -*- coding: utf-8 -*-
# 週間/月間サマリーカード（今日画面先頭）の検証。
# 確認: ①データ投入でカード描画 ②週/月トグル ③無料=大会ペース🔒/プレミアム=表示 ④過去日付で非表示 ⑤シェアcanvasがエラーなし ⑥JSエラー0
import pathlib, sys
from playwright.sync_api import sync_playwright
URI = pathlib.Path('index-v3.html').resolve().as_uri()
results={}
def rec(tc,ok,detail=''): results[tc]=(bool(ok),detail)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel='msedge')
    pg=b.new_page(viewport={'width':414,'height':1000}); pg._errs=[]
    pg.on('pageerror',lambda e:pg._errs.append(str(e)))
    pg.goto(URI,wait_until='load'); pg.evaluate('obFinish()')
    # 今週の日付に記録を投入（体重/睡眠/歩数/PFC/トレ）＋栄養目標＋水分＋大会
    pg.evaluate("""()=>{
      const [s,e]=weekRange(0); const recs=[]; const sd=new Date(s+'T00:00:00');
      for(let i=0;i<4;i++){ const d=new Date(sd); d.setDate(d.getDate()+i); const ds=fmt(d);
        recs.push({date:ds, weight:62.5-i*0.2, sleep:6+i*0.2, steps:8000+i*100, p:120,f:50,c:200,kcal:1800, trained:(i%2===0), muscles:(i%2===0?['胸']:[])}); }
      localStorage.setItem('training_records', JSON.stringify(recs));
      localStorage.setItem('nutrition_goals', JSON.stringify({p:150,f:50,c:250}));
      localStorage.setItem('water_data', JSON.stringify({[recs[0].date]:{total:2000},[recs[1].date]:{total:1800}}));
      localStorage.setItem('contest_date','2026-08-01'); localStorage.setItem('contest_weight','58');
      curDate=logicalToday();
    }""")
    pg.evaluate("go('today')"); pg.wait_for_timeout(150)
    rec('CARD', pg.evaluate("()=>!!document.querySelector('#summary-slot .sumcard')"))
    rec('WEIGHT_DELTA', pg.evaluate("()=>/(-|\\+)?\\d/.test(document.querySelector('.su-w')?.textContent||'')"),
        pg.evaluate("()=>document.querySelector('.su-w')?.textContent.trim()"))
    rec('TRAIN_COUNT', pg.evaluate("()=>(document.querySelector('.su-calh .cnt')?.textContent||'').indexOf('2')>=0"))
    rec('WEEK_CELLS', pg.evaluate("()=>document.querySelectorAll('.su-grid7 .su-cell').length")==7)
    rec('PFC', pg.evaluate("()=>[...document.querySelectorAll('.su-m')].some(m=>m.textContent.indexOf('PFC')>=0 && /\\d%/.test(m.textContent))"))
    # 無料: 大会ペースは🔒
    rec('FREE_LOCKED', pg.evaluate("()=>!!document.querySelector('.su-contest.locked')"))
    # 月トグル
    pg.evaluate("setSummaryPeriod('month')"); pg.wait_for_timeout(60)
    mttl=pg.evaluate("()=>document.querySelector('.su-head .ttl')?.textContent") or ''
    rec('MONTH_TOGGLE', '月' in mttl, f"ttl={mttl}")
    mc=pg.evaluate("()=>document.querySelectorAll('.su-grid7 .su-cell').length")
    rec('MONTH_CELLS', 28<=mc<=42, f"cells={mc}")
    pg.evaluate("setSummaryPeriod('week')")
    # プレミアム: 大会ペース表示
    pg.evaluate("window.AndroidBridge={isPremium:()=>true}; renderSummaryCard();"); pg.wait_for_timeout(50)
    rec('PREM_PACE', pg.evaluate("()=>!!document.querySelector('.su-contest:not(.locked) .pace')"))
    # 過去日付で非表示
    pg.evaluate("window.AndroidBridge=undefined; go('today'); shiftDate(-1);"); pg.wait_for_timeout(60)
    rec('HIDE_PAST', pg.evaluate("()=>document.getElementById('summary-slot').innerHTML===''"))
    # シェアcanvas（ブラウザfallback・anchor clickを無効化してエラーが出ないこと）
    pg.evaluate("go('today'); HTMLAnchorElement.prototype.click=function(){};"); pg.wait_for_timeout(60)
    try:
        pg.evaluate("summaryShare()"); pg.wait_for_timeout(80); share_ok=True
    except Exception as ex:
        share_ok=False
    rec('SHARE_NOERR', share_ok)
    rec('NOERR', not pg._errs, f"{pg._errs[:2]}")
    pg.close(); b.close()
passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
sys.exit(0 if not failed else 1)
