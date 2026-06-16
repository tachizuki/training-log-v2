# -*- coding: utf-8 -*-
# 体重変動分析の要因復活（筋トレ/睡眠/炭水化物/有酸素/歩数）・今日ボタンの「↩今日へ」表示・タブ切替で今日リセット。
import pathlib, sys
from playwright.sync_api import sync_playwright
URI = pathlib.Path('index-v3.html').resolve().as_uri()
results={}
def rec(tc,ok,detail=''): results[tc]=(bool(ok),detail)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel='msedge'); pg=b.new_page(viewport={'width':412,'height':915})
    errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(URI,wait_until='load'); pg.evaluate('obFinish()')

    # 分析: 前日に大筋群トレ/高炭水化物/有酸素/歩数、2日前にもトレ、当日睡眠不足
    pg.evaluate("""()=>{
      const today=logicalToday();
      const d1=new Date(today+'T00:00:00'); d1.setDate(d1.getDate()-1); const prev=fmt(d1);
      const d2=new Date(today+'T00:00:00'); d2.setDate(d2.getDate()-2); const prev2=fmt(d2);
      localStorage.setItem('nutrition_goals', JSON.stringify({p:150,f:40,c:180,salt:5}));
      localStorage.setItem('training_records', JSON.stringify([
        {date:prev2, weight:60.6, trained:true, muscles:['背中']},
        {date:prev, weight:60.4, trained:true, muscles:['足'], c:260, p:150,f:50, kcal:2600, salt:6, cardioKcal:350, steps:12000},
        {date:today, weight:60.0, sleep:5, p:150,f:50,c:200}
      ]));
      curDate=today; renderToday();
    }"""); pg.wait_for_timeout(60)
    h=pg.evaluate("()=>document.getElementById('today-analysis').innerHTML")
    factors={'train':'💪' in h, 'carb':'🍚' in h, 'cardio':'🚴' in h, 'steps':'🚶' in h, 'sleep':'😴' in h}
    nlines=pg.evaluate("()=>document.querySelectorAll('#today-analysis .an-l').length")
    rec('AN-FACTORS', all(factors.values()) and nlines>=7, f'lines={nlines} {factors}')
    rec('AN-TRAIN-BIG', '足' in h or 'Leg' in h, 'big muscle named')
    rec('AN-TRAIN-2D', '2日前' in h or '2 days' in h, 'prev2 training shown')
    rec('AN-NO-REMAIN', ('🎯' not in h) and ('残り' not in h), 'remaining-kcal line removed')
    # ラベルは単一（体重変動分析のみ、今日の分析/サブlabel無し）
    lbl=pg.evaluate("()=>{const t=document.querySelector('[data-i18n=analysis_title]'); const s=document.querySelector('[data-i18n=analysis_sub]'); return {title:t?t.textContent:'', subExists:!!s};}")
    rec('AN-LABEL', ('体重変動分析' in lbl['title']) and ('今日の分析' not in lbl['title']) and (not lbl['subExists']), f"{lbl}")
    rec('AN-ERR', not errs, f'errs={errs[:2]}')

    # 今日ボタン: 今日は非表示、過去日は「↩今日へ」
    pg.evaluate("go('today')"); pg.wait_for_timeout(30)
    onToday=pg.evaluate("()=>getComputedStyle(document.getElementById('btn-today')).display")
    pg.evaluate("shiftDate(-1)"); pg.wait_for_timeout(30)
    off=pg.evaluate("()=>({disp:getComputedStyle(document.getElementById('btn-today')).display, txt:document.getElementById('btn-today').textContent})")
    rec('NAV-BTN-HIDE', onToday=='none', f'on-today display={onToday}')
    rec('NAV-BTN-SHOW', off['disp']!='none' and ('今日へ' in off['txt'] or 'Today' in off['txt']), f"off={off}")

    # 日付リセット: 過去日にしてタブ切替→今日に戻る
    pg.evaluate("shiftDate(-3)"); pg.wait_for_timeout(20)
    past=pg.evaluate("()=>curDate")
    pg.evaluate("go('gym')"); pg.wait_for_timeout(30)
    gymDate=pg.evaluate("()=>curDate")
    pg.evaluate("shiftGymDay(-2)"); pg.wait_for_timeout(20)
    gymPast=pg.evaluate("()=>curDate")
    pg.evaluate("go('today')"); pg.wait_for_timeout(30)
    backToday=pg.evaluate("()=>curDate")
    tdy=pg.evaluate("()=>logicalToday()")
    rec('NAV-RESET', past!=tdy and gymDate==tdy and gymPast!=tdy and backToday==tdy, f'past={past} gym={gymDate} gymPast={gymPast} back={backToday} today={tdy}')

    pg.close(); b.close()

passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
if failed: print('FAILED:', ', '.join(sorted(failed)))
sys.exit(0 if not failed else 1)
