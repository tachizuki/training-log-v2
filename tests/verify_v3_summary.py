# -*- coding: utf-8 -*-
# 週間/月間サマリー（今日画面先頭・アコーディオン＋区切り窓）の検証。
# 仕様: 区切り直後の窓(週=月〜水, 月=月初1〜3日)だけ、完了した期間(先週/先月)を畳んだバーで表示。
#       タップで展開、週/月トグル、×でセッション内非表示、窓外は非表示。無料=大会ペース🔒/プレミアム=表示。
# logicalToday を差し替えて決定論的に検証する。
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
    # 月曜(=週窓)に固定し、先週＋先月の記録を投入
    pg.evaluate("""()=>{
      window.logicalToday=()=>'2026-07-06'; curDate='2026-07-06';
      function mk(range,base){ const [s,e]=range; const sd=new Date(s+'T00:00:00'); const a=[];
        for(let i=0;i<4;i++){ const d=new Date(sd); d.setDate(d.getDate()+i);
          a.push({date:fmt(d), weight:base-i*0.2, sleep:6+i*0.2, steps:8000+i*100, p:120,f:50,c:200,kcal:1800, trained:(i%2===0), muscles:(i%2===0?['胸']:[])}); } return a; }
      const recs=[...mk(weekRange(-1),62.5), ...mk(monthRange(-1),64.0)];
      localStorage.setItem('training_records', JSON.stringify(recs));
      localStorage.setItem('nutrition_goals', JSON.stringify({p:150,f:50,c:250}));
      localStorage.setItem('contest_date','2026-08-01'); localStorage.setItem('contest_weight','58');
    }""")
    pg.evaluate("renderSummaryCard()"); pg.wait_for_timeout(80)
    # 既定は畳んだバー（先週のまとめ）／フルカードは出ていない
    rec('BAR', pg.evaluate("()=>!!document.querySelector('.sumbar')"))
    btt=pg.evaluate("()=>document.querySelector('.sumbar .bttl')?.textContent") or ''
    rec('BAR_LASTWEEK', '先週' in btt, f"ttl={btt}")
    rec('COLLAPSED_NO_CARD', pg.evaluate("()=>!document.querySelector('.sumcard')"))
    # タップで展開
    pg.evaluate("toggleSummary()"); pg.wait_for_timeout(60)
    rec('EXPAND', pg.evaluate("()=>!!document.querySelector('.sumcard')"))
    rec('WEIGHT_DELTA', pg.evaluate("()=>/(-|\\+)?\\d/.test(document.querySelector('.su-w')?.textContent||'')"),
        pg.evaluate("()=>document.querySelector('.su-w')?.textContent.trim()"))
    rec('TRAIN_COUNT', pg.evaluate("()=>(document.querySelector('.su-calh .cnt')?.textContent||'').indexOf('2')>=0"))
    rec('WEEK_CELLS', pg.evaluate("()=>document.querySelectorAll('.su-grid7 .su-cell').length")==7)
    rec('PFC', pg.evaluate("()=>[...document.querySelectorAll('.su-m')].some(m=>m.textContent.indexOf('PFC')>=0 && /\\d%/.test(m.textContent))"))
    rec('FREE_LOCKED', pg.evaluate("()=>!!document.querySelector('.su-contest.locked')"))
    # 週→月トグルで「先月のまとめ」
    pg.evaluate("setSummaryPeriod('month')"); pg.wait_for_timeout(60)
    mtt=pg.evaluate("()=>document.querySelector('.su-head .ttl')?.textContent") or ''
    rec('MONTH_TOGGLE', '先月' in mtt, f"ttl={mtt}")
    rec('MONTH_CELLS', 28<=pg.evaluate("()=>document.querySelectorAll('.su-grid7 .su-cell').length")<=42)
    pg.evaluate("setSummaryPeriod('week')")
    # プレミアム: 大会ペース表示
    pg.evaluate("window.AndroidBridge={isPremium:()=>true}; renderSummaryCard();"); pg.wait_for_timeout(50)
    rec('PREM_PACE', pg.evaluate("()=>!!document.querySelector('.su-contest:not(.locked) .pace')"))
    pg.evaluate("window.AndroidBridge=undefined;")
    # 折りたたみへ戻す
    pg.evaluate("toggleSummary(); renderSummaryCard();"); pg.wait_for_timeout(40)
    rec('COLLAPSE_BACK', pg.evaluate("()=>!!document.querySelector('.sumbar') && !document.querySelector('.sumcard')"))
    # ×で非表示 → 同セッションは再renderでも非表示
    pg.evaluate("dismissSummary()"); pg.wait_for_timeout(40)
    pg.evaluate("renderSummaryCard()")
    rec('DISMISS_SESSION', pg.evaluate("()=>document.getElementById('summary-slot').innerHTML===''"))
    # 窓外(木曜・dom>3)は非表示
    pg.evaluate("summaryHidden=false; window.logicalToday=()=>'2026-07-09'; curDate='2026-07-09'; renderSummaryCard();"); pg.wait_for_timeout(40)
    rec('OUT_OF_WINDOW_HIDDEN', pg.evaluate("()=>document.getElementById('summary-slot').innerHTML===''"))
    # 月初(7/1)は先月のまとめが窓に出る
    pg.evaluate("window.logicalToday=()=>'2026-07-01'; curDate='2026-07-01'; renderSummaryCard();"); pg.wait_for_timeout(40)
    m1=pg.evaluate("()=>document.querySelector('.sumbar .bttl')?.textContent") or ''
    rec('MONTH_START_LASTMONTH', '先月' in m1, f"ttl={m1}")
    # シェアcanvas（展開状態・anchor click無効化でエラー無し）
    pg.evaluate("window.logicalToday=()=>'2026-07-06'; curDate='2026-07-06'; summaryExpanded=true; HTMLAnchorElement.prototype.click=function(){}; renderSummaryCard();"); pg.wait_for_timeout(40)
    try:
        pg.evaluate("summaryShare()"); pg.wait_for_timeout(60); share_ok=True
    except Exception as ex:
        share_ok=False
    rec('SHARE_NOERR', share_ok)
    rec('NOERR', not pg._errs, f"{pg._errs[:2]}")
    pg.close(); b.close()
passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
sys.exit(0 if not failed else 1)
