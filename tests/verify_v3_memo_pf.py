# -*- coding: utf-8 -*-
# 旧版から復活: 体重変動分析の脂質(🫒)/タンパク質(🥩)要因 + 当日メモ入力→翌日メモ解析(飲み会/外食/アウトドア)。
import pathlib, sys
from playwright.sync_api import sync_playwright
URI = pathlib.Path('index-v3.html').resolve().as_uri()
results={}
def rec(tc,ok,detail=''): results[tc]=(bool(ok),detail)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel='msedge')
    pg=b.new_page(viewport={'width':412,'height':915}); pg._errs=[]
    pg.on('pageerror',lambda e:pg._errs.append(str(e)))
    pg.goto(URI,wait_until='load'); pg.evaluate('obFinish()')
    # 目標 P160/F50/C230
    pg.evaluate("()=>localStorage.setItem('nutrition_goals', JSON.stringify({p:160,f:50,c:230,salt:6}))")
    def setup(prev):
        pg.evaluate(f"""()=>{{
          const t=logicalToday(); const d=new Date(t+'T00:00:00'); d.setDate(d.getDate()-1);
          const z=n=>String(n).padStart(2,'0'); const y=d.getFullYear()+'-'+z(d.getMonth()+1)+'-'+z(d.getDate());
          const prev=Object.assign({{date:y, weight:61}}, {prev});
          localStorage.setItem('training_records', JSON.stringify([prev, {{date:t, weight:60.8}}]));
        }}""")
        pg.evaluate("go('today'); curDate=logicalToday(); renderToday();"); pg.wait_for_timeout(40)
        return pg.evaluate("()=>document.getElementById('today-analysis').innerHTML")

    # 脂質 高め(110>50+50→bad 🫒) / タンパク質 不足(80<160-40→warn 🥩)
    h=setup("{p:80,f:110,c:200}")
    rec('FAT_HIGH', ('🫒' in h) and ('脂質' in h), '')
    rec('PROTEIN_LOW', ('🥩' in h) and ('不足' in h), '')
    # 脂質 少なめ(20<50-20) / タンパク質 十分(170>=160)
    h2=setup("{p:170,f:20,c:230}")
    rec('FAT_LOW', ('🫒' in h2) and ('少なめ' in h2), '')
    rec('PROTEIN_OK', ('🥩' in h2) and ('十分' in h2), '')
    # メモ解析: 前日メモ「飲み会で焼肉」→ 🍺飲み会 + 🍜外食
    h3=setup("{p:160,f:50,c:230,memo:'飲み会で焼肉'}")
    rec('MEMO_DRINK', ('🍺' in h3), '')
    rec('MEMO_EAT', ('🍜' in h3), '')
    # メモ入力欄が存在し、入力→保存→再描画で値が残る
    pg.evaluate("go('today'); curDate=logicalToday();")
    pg.evaluate("()=>{const e=document.getElementById('today-memo'); e.value='旅行に行った'; saveTodayMemo(e.value);}")
    saved=pg.evaluate("()=>{const r=(JSON.parse(localStorage.getItem('training_records'))||[]).find(x=>x.date===logicalToday()); return r&&r.memo;}")
    rec('MEMO_INPUT_SAVED', saved=='旅行に行った', f"saved={saved}")
    rec('NOERR', not pg._errs, f"{pg._errs[:2]}")
    pg.close(); b.close()
failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len([k for k,v in results.items() if v[0]])}/{len(results)} PASS ===")
sys.exit(0 if not failed else 1)
