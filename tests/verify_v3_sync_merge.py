# -*- coding: utf-8 -*-
# 多端末クラウド同期の競合解消: 日付ごとの更新時刻uで新しい方を採用（記録/水分/筋トレ）。
import pathlib, sys
from playwright.sync_api import sync_playwright
URI = pathlib.Path('index-v3.html').resolve().as_uri()
results={}
def rec(tc,ok,detail=''): results[tc]=(bool(ok),detail)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel='msedge'); pg=b.new_page(viewport={'width':412,'height':915})
    pg._errs=[]; pg.on('pageerror',lambda e:pg._errs.append(str(e)))
    pg.goto(URI,wait_until='load'); pg.evaluate('obFinish()')

    # training_records: 端末2(古・栄養なし) ← クラウド(新・栄養あり)
    local=[{'date':'2026-06-16','weight':60,'u':1000},
           {'date':'2026-06-14','weight':62,'u':5000}]                 # ローカルが新しい日
    cloud=[{'date':'2026-06-16','weight':60,'p':150,'f':50,'c':200,'kcal':2180,'u':2000},  # 端末1: 新しい・栄養入り
           {'date':'2026-06-15','weight':61,'u':1500},                  # クラウドにしか無い日
           {'date':'2026-06-14','weight':60,'u':3000}]                  # 古いクラウド
    pg.evaluate("""(a)=>{ localStorage.setItem('training_records', JSON.stringify(a.local));
        receiveFirestoreData(JSON.stringify({training_records: JSON.stringify(a.cloud)})); }""", {'local':local,'cloud':cloud})
    out=pg.evaluate("()=>JSON.parse(localStorage.getItem('training_records'))")
    m={r['date']:r for r in out}
    rec('SY-NUTRI', m.get('2026-06-16',{}).get('p')==150 and m.get('2026-06-16',{}).get('kcal')==2180, f"16th={m.get('2026-06-16')}")
    rec('SY-NEWDATE', '2026-06-15' in m and m['2026-06-15'].get('weight')==61, 'cloud-only date added')
    rec('SY-LOCALWINS', m.get('2026-06-14',{}).get('weight')==62, f"local newer kept={m.get('2026-06-14')}")

    # water_data: 日付ごと新しい方
    lw={'2026-06-16':{'total':500,'log':[],'u':1000}}
    cw={'2026-06-16':{'total':1500,'log':[],'u':2000},'2026-06-15':{'total':800,'log':[],'u':900}}
    pg.evaluate("""(a)=>{ localStorage.setItem('water_data', JSON.stringify(a.lw));
        receiveFirestoreData(JSON.stringify({water_data: JSON.stringify(a.cw)})); }""", {'lw':lw,'cw':cw})
    w=pg.evaluate("()=>JSON.parse(localStorage.getItem('water_data'))")
    rec('SY-WATER', w.get('2026-06-16',{}).get('total')==1500 and '2026-06-15' in w, f"{w}")

    # gym_data: 日付ごと新しい方
    lg={'2026-06-16':{'exercises':[{'name':'ベンチプレス','sets':[{'weight':60,'reps':8}]}],'u':1000}}
    cg={'2026-06-16':{'exercises':[{'name':'スクワット','sets':[{'weight':100,'reps':5}]}],'u':2000}}
    pg.evaluate("""(a)=>{ localStorage.setItem('gym_data', JSON.stringify(a.lg));
        receiveFirestoreData(JSON.stringify({gym_data: JSON.stringify(a.cg)})); }""", {'lg':lg,'cg':cg})
    g=pg.evaluate("()=>JSON.parse(localStorage.getItem('gym_data'))['2026-06-16'].exercises[0].name")
    rec('SY-GYM', g=='スクワット', f'gym newer wins name={g}')

    rec('SY-ERR', not pg._errs, f'errs={pg._errs[:2]}')
    pg.close(); b.close()

passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
if failed: print('FAILED:', ', '.join(sorted(failed)))
sys.exit(0 if not failed else 1)
