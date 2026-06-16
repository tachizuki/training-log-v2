# -*- coding: utf-8 -*-
# 「アプリ設定」セクション新設の検証：起点時刻/リマインダー/言語を集約、プロフィール・サポートから除去。
import pathlib, sys
from playwright.sync_api import sync_playwright
URI = pathlib.Path('index-v3.html').resolve().as_uri()
results={}
def rec(tc,ok,detail=''): results[tc]=(bool(ok),detail)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel='msedge'); pg=b.new_page(viewport={'width':412,'height':915})
    errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(URI,wait_until='load'); pg.evaluate('obFinish()'); pg.evaluate("go('set')"); pg.wait_for_timeout(60)

    # セクション見出しに「アプリ設定」が存在
    secs=pg.evaluate("()=>[...document.querySelectorAll('#pg-set .set-sec')].map(e=>e.textContent.trim())")
    rec('A-SEC01', any('アプリ設定' in s or 'App settings' in s for s in secs), f'secs={secs}')

    # 各入力がどのセクションのカードに属するか（直後の set-card 内に存在するか）で判定
    def card_of(label_jp):
        return pg.evaluate("""(lbl)=>{
            const secs=[...document.querySelectorAll('#pg-set .set-sec')];
            for(const s of secs){ const card=s.nextElementSibling; if(card && card.classList.contains('set-card')){
              const hit=[...card.querySelectorAll('[data-i18n],label')].some(()=>false);
            }}
            // 各idがどのセクション見出しの配下かを探す
            const find=(id)=>{ const el=document.getElementById(id); if(!el) return null; let card=el.closest('.set-card'); if(!card) return null; let sec=card.previousElementSibling; return sec?sec.textContent.trim():null; };
            return find(lbl);
        }""", label_jp)
    sec_lang=card_of('set-lang'); sec_ds=card_of('set-day-start'); sec_nt=card_of('set-notif-time'); sec_sex=card_of('set-sex')
    rec('A-SEC02', sec_ds and ('アプリ設定' in sec_ds or 'App' in sec_ds), f'day-start under {sec_ds}')
    rec('A-SEC03', sec_nt and ('アプリ設定' in sec_nt or 'App' in sec_nt), f'reminder under {sec_nt}')
    rec('A-SEC04', sec_lang and ('アプリ設定' in sec_lang or 'App' in sec_lang), f'lang under {sec_lang}')
    rec('A-SEC05', sec_sex and ('プロフィール' in sec_sex or 'Profile' in sec_sex), f'sex under {sec_sex}')

    # プロフィールカードに起点/通知が無いこと（=移動済み）
    prof_has=pg.evaluate("""()=>{const sex=document.getElementById('set-sex'); const card=sex.closest('.set-card'); return {ds:!!card.querySelector('#set-day-start'), nt:!!card.querySelector('#set-notif-time')};}""")
    rec('A-SEC06', not prof_has['ds'] and not prof_has['nt'], f'profile leftover={prof_has}')

    # 機能維持: 言語切替・起点時刻保存・性別保存
    pg.evaluate("setLang('en')"); pg.wait_for_timeout(30); en=pg.evaluate("()=>t('weight')")
    pg.evaluate("setLang('ja')"); pg.wait_for_timeout(30); ja=pg.evaluate("()=>t('weight')")
    rec('A-FN01', en=='Weight' and ja=='体重', f'lang ok en={en} ja={ja}')
    pg.evaluate("()=>{const e=document.getElementById('set-day-start'); if(e.options.length){e.value=String(Math.min(4,e.options.length-1)); e.dispatchEvent(new Event('change'));}}"); pg.wait_for_timeout(40)
    rec('A-FN02', pg.evaluate("()=>localStorage.getItem('day_start_hour')!==null"), 'day_start saved')
    pg.evaluate("()=>{const e=document.getElementById('set-sex'); e.value='female'; e.dispatchEvent(new Event('change'));}"); pg.wait_for_timeout(40)
    rec('A-FN03', pg.evaluate("()=>JSON.parse(localStorage.getItem('user_profile')||'{}').sex")=='female', 'sex saved')

    rec('A-ERR', not errs, f'errs={errs[:2]}')
    pg.close(); b.close()

passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
if failed: print('FAILED:', ', '.join(sorted(failed)))
sys.exit(0 if not failed else 1)
