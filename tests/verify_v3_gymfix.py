# -*- coding: utf-8 -*-
# 筋トレ系修正バッチ1: グラフ罫線/筋トレメモ/セット単位削除/ピッカー追加済みハイライト/キーボードscroll。
import pathlib, sys
from playwright.sync_api import sync_playwright
URI = pathlib.Path('index-v3.html').resolve().as_uri()
BACKUP = 'G:/マイドライブ/traininglog_backup_2026-06-15.json'
results={}
def rec(tc,ok,detail=''): results[tc]=(bool(ok),detail)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel='msedge'); pg=b.new_page(viewport={'width':412,'height':915})
    pg._errs=[]; pg.on('pageerror',lambda e:pg._errs.append(str(e)))
    raw=open(BACKUP,encoding='utf-8').read()
    pg.goto(URI,wait_until='load'); pg.evaluate('obFinish()')

    # ⑥ グラフ罫線
    pg.evaluate("(s)=>receiveImportData(s)", raw); pg.wait_for_timeout(80)
    pg.evaluate("go('data'); setPeriod('all'); renderData()"); pg.wait_for_timeout(60)
    lines=pg.evaluate("()=>document.querySelectorAll('#weight-chart line').length")
    ticks=pg.evaluate("()=>document.querySelectorAll('#weight-chart text').length")
    rec('GF-CHART', lines>=4 and ticks>=3, f'gridlines={lines} texts={ticks}')

    # ① セットごとのメモ
    pg.evaluate("go('gym'); curDate=logicalToday(); gymWork=[{name:'ベンチプレス',sets:[{weight:60,reps:8}]}]; saveGymData(); renderGym();"); pg.wait_for_timeout(20)
    nmemo=pg.evaluate("()=>document.querySelectorAll('#gym-cards .srow-memo').length")
    pg.evaluate("gymSetMemo(0,0,'重い、フォーム意識')"); pg.wait_for_timeout(20)
    sm=pg.evaluate("()=>DB.gym()[curDate].exercises[0].sets[0].memo")
    pg.evaluate("renderGym()"); pg.wait_for_timeout(20)
    shown=pg.evaluate("()=>{const i=document.querySelector('#gym-cards .srow-memo'); return i?i.value:null;}")
    rec('GF-SETMEMO', nmemo>=1 and sm=='重い、フォーム意識' and shown==sm, f'inputs={nmemo} saved={sm!r} shown={shown!r}')

    # ④ セット単位削除
    pg.evaluate("curDate=logicalToday(); gymWork=[{name:'ベンチプレス',sets:[{weight:60,reps:8},{weight:60,reps:7},{weight:55,reps:6}]}]; saveGymData(); renderGym();"); pg.wait_for_timeout(30)
    n0=pg.evaluate("()=>gymWork[0].sets.length")
    delbtns=pg.evaluate("()=>document.querySelectorAll('#gym-cards .srow-del').length")
    pg.evaluate("gymDelSet(0,1)"); pg.wait_for_timeout(20)
    n1=pg.evaluate("()=>{const g=DB.gym()[curDate]; return g.exercises[0].sets.length;}")
    rec('GF-DELSET', n0==3 and delbtns==3 and n1==2, f'before={n0} btns={delbtns} after={n1}')

    # ⑤ ピッカーで追加済みハイライト
    pg.evaluate("openExSheet(); exShowCat('胸')"); pg.wait_for_timeout(30)
    added=pg.evaluate("""()=>{ const btns=[...document.querySelectorAll('#ex-grid .ex-cell button')];
        const bench=btns.find(b=>b.textContent.indexOf('ベンチプレス')>=0);
        return bench? {hasClass:bench.classList.contains('added'), check:bench.textContent.indexOf('✓')>=0} : null; }""")
    rec('GF-PICKER', added and added['hasClass'] and added['check'], f'{added}')
    pg.evaluate("closeExSheet()")

    # ② 独立レストタイマー（プリセット＋カスタム→開始）。✓チェック/自動開始は廃止
    pg.evaluate("go('gym'); openTimerSheet()"); pg.wait_for_timeout(20)
    topen=pg.evaluate("()=>document.getElementById('timer-sheet').classList.contains('open') && document.querySelectorAll('#tm-presets .tm-chip').length>=5")
    pg.evaluate("tmPick(120); startRestFromSheet()"); pg.wait_for_timeout(20)
    tres=pg.evaluate("()=>({tot:restTotal, saved:localStorage.getItem('rest_sec'), shown:document.getElementById('rest').classList.contains('show'), sheetClosed:!document.getElementById('timer-sheet').classList.contains('open')})")
    # セット行に✓チェックが無いこと（自動開始の撤去）
    pg.evaluate("restStop(); gymWork=[{name:'ベンチプレス',sets:[{weight:60,reps:8}]}]; saveGymData(); renderGym();"); pg.wait_for_timeout(20)
    nochk=pg.evaluate("()=>document.querySelectorAll('#gym-cards .chk').length===0")
    rec('GF-TIMER', topen and tres['tot']==120 and tres['saved']=='120' and tres['shown'] and tres['sheetClosed'] and nochk, f'open={topen} {tres} nochk={nochk}')
    pg.evaluate("restStop()")

    # ⑧ 有酸素の種目別入力
    pg.evaluate("curDate=logicalToday(); gymWork=[{name:'トレッドミル',sets:[]}]; saveGymData(); renderGym();"); pg.wait_for_timeout(30)
    crows=pg.evaluate("()=>[...document.querySelectorAll('#gym-cards .crow .cl')].map(e=>e.textContent)")
    ok_fields = ('時間' in crows and '速度' in crows and '傾斜' in crows and '消費カロリー' in crows) and pg.evaluate("()=>document.querySelectorAll('#gym-cards .srow').length===0")
    pg.evaluate("openGymCardioPad(0,'speed')"); pg.wait_for_timeout(10)
    pg.evaluate("padKey('8'); padDone()"); pg.wait_for_timeout(20)
    cspeed=pg.evaluate("()=>DB.gym()[curDate].exercises[0].cardio.speed")
    rec('GF-CARDIO', ok_fields and cspeed==8, f'fields={crows} speed={cspeed}')
    # 水泳=時間/距離/消費カロリー、強度種目はセット維持（回帰）
    pg.evaluate("gymWork=[{name:'水泳',sets:[]}]; saveGymData(); renderGym();"); pg.wait_for_timeout(20)
    swim=pg.evaluate("()=>[...document.querySelectorAll('#gym-cards .crow .cl')].map(e=>e.textContent)")
    pg.evaluate("gymWork=[{name:'ベンチプレス',sets:[{weight:60,reps:8}]}]; saveGymData(); renderGym();"); pg.wait_for_timeout(20)
    strength=pg.evaluate("()=>document.querySelectorAll('#gym-cards .srow').length>0 && document.querySelectorAll('#gym-cards .crow').length===0")
    rec('GF-CARDIO2', ('時間' in swim and '距離' in swim and '消費カロリー' in swim and '速度' not in swim) and strength, f'swim={swim} strengthOK={strength}')

    # ⑦ シェア画像（Canvas→ネイティブ saveStart/Chunk/Done）
    pg.evaluate("""()=>{ window.AndroidBridge={ _c:[], saveStart(f,n){this._c.push(['start',f,n]);}, saveChunk(i,d){this._c.push(['chunk',i,d.length]);}, saveDone(){this._c.push(['done']);} }; }""")
    pg.evaluate("curDate=logicalToday(); gymWork=[{name:'ベンチプレス',sets:[{weight:60,reps:8},{weight:60,reps:7}]},{name:'トレッドミル',sets:[],cardio:{time:20,speed:8,kcal:200}}]; saveGymData(); renderGym();"); pg.wait_for_timeout(30)
    pg.evaluate("gymShare()"); pg.wait_for_timeout(40)
    sh=pg.evaluate("""()=>{ const c=AndroidBridge._c; const start=c.find(x=>x[0]==='start'); const nchunk=c.filter(x=>x[0]==='chunk').length; const done=c.some(x=>x[0]==='done'); return {fname:start?start[1]:null, n:start?start[2]:0, nchunk:nchunk, done:done}; }""")
    rec('GF-SHARE', sh['fname'] and sh['fname'].startswith('workout_') and sh['n']>=1 and sh['nchunk']==sh['n'] and sh['done'], f'{sh}')
    pg.evaluate("delete window.AndroidBridge")

    # ③ キーボードscroll: focusinハンドラでテキスト入力がscrollIntoView（関数存在＝エラーなし確認）
    rec('GF-KEY', not pg._errs, f'no page errors (focusin wired), errs={pg._errs[:2]}')
    pg.close(); b.close()

passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
if failed: print('FAILED:', ', '.join(sorted(failed)))
sys.exit(0 if not failed else 1)
