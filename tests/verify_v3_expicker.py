# -*- coding: utf-8 -*-
# 種目追加ピッカー（カテゴリ別・固定高・編集削除・カスタム追加・検索・移行）の検証。
import pathlib, sys
from playwright.sync_api import sync_playwright
URI = pathlib.Path('index-v3.html').resolve().as_uri()
results={}
def rec(tc,ok,detail=''): results[tc]=(bool(ok),detail)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel='msedge')
    def newpage():
        pg=b.new_page(viewport={'width':412,'height':915}); pg._errs=[]; pg._dialog='accept'
        pg.on('pageerror',lambda e:pg._errs.append(str(e)))
        pg.on('dialog', lambda d: d.accept() if pg._dialog=='accept' else d.dismiss())
        pg.goto(URI,wait_until='load'); pg.evaluate('obFinish()'); pg.evaluate("go('gym'); curDate=logicalToday();")
        return pg

    pg=newpage()
    pg.evaluate("openExSheet()"); pg.wait_for_timeout(40)
    st=pg.evaluate("()=>({open:document.getElementById('ex-sheet').classList.contains('open'), cats:[...document.querySelectorAll('.ex-cat')].map(e=>e.textContent), grid:document.querySelectorAll('#ex-grid .ex-cell').length, glabel:document.getElementById('ex-glabel').textContent})")
    rec('E-OPEN', st['open'] and len(st['cats'])==7 and st['grid']==7 and st['glabel']=='胸', f"cats={len(st['cats'])} grid={st['grid']} label={st['glabel']}")

    # 高さ一定（胸7種 vs 背中8種で .ex-grid の高さが同じ）
    h1=pg.evaluate("()=>document.querySelector('.ex-grid').clientHeight")
    pg.evaluate("exShowCat('背中')"); pg.wait_for_timeout(30)
    h2=pg.evaluate("()=>document.querySelector('.ex-grid').clientHeight")
    g2=pg.evaluate("()=>document.querySelectorAll('#ex-grid .ex-cell').length")
    rec('E-HEIGHT', h1>0 and h1==h2, f'h1={h1} h2={h2}')
    rec('E-CAT', g2==8 and pg.evaluate("()=>document.getElementById('ex-glabel').textContent")=='背中', f'back grid={g2}')

    # 検索（全部位横断: 「カール」は腕に複数）
    pg.evaluate("()=>{const q=document.getElementById('ex-q'); q.value='カール'; exSearch();}"); pg.wait_for_timeout(30)
    sres=pg.evaluate("()=>({n:document.querySelectorAll('#ex-grid .ex-cell').length, onchip:document.querySelectorAll('.ex-cat.on').length})")
    rec('E-SEARCH', sres['n']>=4 and sres['onchip']==0, f"search n={sres['n']} chips_on={sres['onchip']}")

    # カスタム追加（胸へ）→ 即グリッド反映＋永続化
    pg.evaluate("exShowCat('胸')"); pg.wait_for_timeout(20)
    pg.evaluate("()=>{const i=document.getElementById('ex-cust'); i.value='マイベンチ'; exAddCustom();}"); pg.wait_for_timeout(30)
    added=pg.evaluate("()=>{const names=[...document.querySelectorAll('#ex-grid .ex-cell button')].map(b=>b.textContent); const saved=JSON.parse(localStorage.getItem('gym_presets')); return {inGrid:names.includes('マイベンチ'), inStore:(saved['胸']||[]).includes('マイベンチ')};}")
    rec('E-CUSTOM', added['inGrid'] and added['inStore'], f"{added}")

    # 編集→削除（永続化）
    pg.evaluate("exToggleEdit()"); pg.wait_for_timeout(20)
    editing=pg.evaluate("()=>document.getElementById('ex-sheet').classList.contains('editing')")
    pg.evaluate("exDel('マイベンチ')"); pg.wait_for_timeout(30)
    deleted=pg.evaluate("()=>{const saved=JSON.parse(localStorage.getItem('gym_presets')); return !(saved['胸']||[]).includes('マイベンチ');}")
    rec('E-DEL', editing and deleted, f'editing={editing} deleted={deleted}')

    # 戻す確認: キャンセル時は戻らない（アプリ内ダイアログをキャンセル）
    pg.evaluate("exDel('ベンチプレス'); exResetCat(); closeConfirm()"); pg.wait_for_timeout(30)
    not_reset=pg.evaluate("()=>!JSON.parse(localStorage.getItem('gym_presets'))['胸'].includes('ベンチプレス')")
    rec('E-RESET-CANCEL', not_reset, 'cancel -> not reset')
    # 戻す確認: OK時は戻る（アプリ内ダイアログのOK）
    pg.evaluate("exResetCat(); document.getElementById('confirm-ok').click()"); pg.wait_for_timeout(30)
    reset_ok=pg.evaluate("()=>JSON.parse(localStorage.getItem('gym_presets'))['胸'].includes('ベンチプレス')")
    rec('E-RESET', reset_ok, 'OK -> reset restores defaults')
    # ✕ボタンがセル内側に配置（負オフセットでない＝見切れ対策）
    delpos=pg.evaluate("()=>{const d=document.querySelector('.ex-cell .del'); const cs=getComputedStyle(d); return {top:cs.top, right:cs.right};}")
    rec('E-DELPOS', delpos['top']=='4px' and delpos['right']=='4px', f'del pos={delpos}')

    # 種目を選ぶ→gymWorkに追加＋シート閉じる
    pg.evaluate("exToggleEdit()") # 編集解除
    n0=pg.evaluate("()=>gymWork.length")
    pg.evaluate("pickEx('ベンチプレス')"); pg.wait_for_timeout(30)
    pick=pg.evaluate("()=>({len:gymWork.length, last:gymWork[gymWork.length-1]&&gymWork[gymWork.length-1].name, closed:!document.getElementById('ex-sheet').classList.contains('open')})")
    rec('E-PICK', pick['len']==n0+1 and pick['last']=='ベンチプレス' and pick['closed'], f"{pick}")
    # 前回コピーボタンのスタイル（既定ボタンでなくテーマ適用＝枠線あり）＋ 削除アイコン別クラス
    pg.evaluate("curDate=logicalToday(); gymWork=[{name:'ベンチプレス',sets:[{weight:60,reps:8}]}]; saveGymData(); renderGym();"); pg.wait_for_timeout(30)
    btn=pg.evaluate("()=>{const cp=document.querySelector('.copy-prev'); const del=document.querySelector('.ex-del-btn'); if(!cp) return null; const cs=getComputedStyle(cp); return {bw:cs.borderTopWidth, hasDel:!!del, txt:cp.textContent.trim()};}")
    rec('E-COPYBTN', btn and btn['bw']!='0px' and btn['hasDel'], f"{btn}")
    rec('E-ERR', not pg._errs, f'errs={pg._errs[:2]}')
    pg.close()

    # 旧フラット配列からの移行
    pg=newpage()
    pg.evaluate("()=>{ localStorage.setItem('gym_presets', JSON.stringify(['マイ種目A','マイ種目B'])); openExSheet(); }"); pg.wait_for_timeout(40)
    mig=pg.evaluate("()=>{const s=JSON.parse(localStorage.getItem('gym_presets')); return {obj:(typeof s==='object'&&!Array.isArray(s)), chest:Array.isArray(s['胸']), other:(s['その他']||[]).includes('マイ種目A')};}")
    rec('E-MIGRATE', mig['obj'] and mig['chest'] and mig['other'], f"{mig}")
    pg.close()

    # i18n EN
    pg=newpage()
    pg.evaluate("setLang('en'); openExSheet()"); pg.wait_for_timeout(40)
    en=pg.evaluate("()=>({edit:document.getElementById('ex-edit-btn').textContent, ph:document.getElementById('ex-q').placeholder, add:t('ex_add_to','Chest')})")
    rec('E-I18N', en['edit']=='Edit' and 'Search' in en['ph'] and 'Chest' in en['add'], f"{en}")
    pg.close()
    b.close()

passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
if failed: print('FAILED:', ', '.join(sorted(failed)))
sys.exit(0 if not failed else 1)
