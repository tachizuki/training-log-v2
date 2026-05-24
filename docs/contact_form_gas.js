/**
 * PhysiqueLog — お問い合わせ受信スクリプト
 * Google Apps Script (GAS) Web App
 *
 * ═══ 設置手順 ═══
 * 1. スプレッドシートを開く
 *    https://docs.google.com/spreadsheets/d/1ZETBoAxGFsi8kOvYwhl7avOE-vZx-Lkez_46JgP8ds8
 * 2. メニュー「拡張機能」→「Apps Script」
 * 3. このファイルの内容を全てコピーして貼り付け（既存のコードは削除）
 * 4. 「保存」（Ctrl+S）
 * 5. 「デプロイ」→「新しいデプロイ」
 *    - 種類: ウェブアプリ
 *    - 次のユーザーとして実行: 自分
 *    - アクセスできるユーザー: 全員
 * 6. 「デプロイ」→ 認証を許可
 * 7. 表示された URL を CONTACT_GAS_URL に設定
 *
 * ※ Android アプリは GET ?payload=<JSON> で送信します（POST redirect 問題を回避）
 */

const SPREADSHEET_ID = '1ZETBoAxGFsi8kOvYwhl7avOE-vZx-Lkez_46JgP8ds8';
const NOTIFY_EMAIL   = 'physiquelog.support@gmail.com';
const SHEET_NAME     = 'お問い合わせ';

function getSheet() {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow(['受信日時', '種類', 'タイトル', '内容', 'バージョン', 'ログイン', 'プレミアム', '言語', 'UA']);
    sheet.getRange(1, 1, 1, 9).setFontWeight('bold').setBackground('#3c3c3c').setFontColor('#ffffff');
    sheet.setFrozenRows(1);
    sheet.setColumnWidth(1, 150); sheet.setColumnWidth(3, 200);
    sheet.setColumnWidth(4, 350); sheet.setColumnWidth(9, 300);
  }
  return sheet;
}

// ───────────────────────────────
// GET リクエスト（Android アプリから ?payload=<JSON> で届く）
// ───────────────────────────────
function doGet(e) {
  // payload パラメータがある場合 → フォーム送信として処理
  if (e && e.parameter && e.parameter.payload) {
    return processContact(e.parameter.payload);
  }
  // ブラウザ直接アクセス用の確認メッセージ
  return ContentService
    .createTextOutput('PhysiqueLog Contact Form Endpoint is running ✓')
    .setMimeType(ContentService.MimeType.TEXT);
}

// POST も念のため受け付ける（ブラウザ版 fetch 用）
function doPost(e) {
  const raw = (e && e.postData && e.postData.contents) ? e.postData.contents : '';
  if (raw) return processContact(raw);
  return ContentService
    .createTextOutput(JSON.stringify({ ok: false, error: 'no body' }))
    .setMimeType(ContentService.MimeType.JSON);
}

function processContact(payloadStr) {
  const sheet = getSheet();
  const now   = new Date();
  try {
    const data     = JSON.parse(payloadStr);
    const catLabels = {
      bug: '🐛 不具合報告', feature: '💡 機能要望',
      payment: '💳 課金・サブスク', account: '👤 アカウント・データ', other: '❓ その他'
    };
    const catLabel = catLabels[data.category] || data.category || '—';

    sheet.appendRow([
      now, catLabel,
      data.subject  || '',
      data.body     || '',
      data.meta?.version  || '',
      data.meta?.loggedIn || '',
      data.meta?.premium  || '',
      data.meta?.lang     || '',
      data.meta?.ua       || ''
    ]);

    const subject   = `[PhysiqueLog] ${catLabel}｜${data.subject}`;
    const plainBody =
      `種類: ${catLabel}\nタイトル: ${data.subject}\n\n── 内容 ──\n${data.body}\n\n` +
      `── システム情報 ──\nバージョン: ${data.meta?.version}\nログイン: ${data.meta?.loggedIn}\n` +
      `プレミアム: ${data.meta?.premium}\n言語: ${data.meta?.lang}\n`;
    const htmlBody =
      `<div style="font-family:sans-serif;max-width:600px;">` +
      `<h2 style="color:#333;">📧 新しいお問い合わせ</h2>` +
      `<table style="border-collapse:collapse;width:100%;">` +
      `<tr style="background:#f5f5f5;"><th style="padding:8px 12px;border:1px solid #ddd;text-align:left;width:120px;">種類</th><td style="padding:8px 12px;border:1px solid #ddd;">${catLabel}</td></tr>` +
      `<tr><th style="padding:8px 12px;border:1px solid #ddd;text-align:left;">タイトル</th><td style="padding:8px 12px;border:1px solid #ddd;">${data.subject}</td></tr>` +
      `<tr style="background:#f5f5f5;"><th style="padding:8px 12px;border:1px solid #ddd;text-align:left;vertical-align:top;">内容</th><td style="padding:8px 12px;border:1px solid #ddd;white-space:pre-wrap;">${data.body}</td></tr>` +
      `<tr><th style="padding:8px 12px;border:1px solid #ddd;text-align:left;">バージョン</th><td style="padding:8px 12px;border:1px solid #ddd;">${data.meta?.version || '—'}</td></tr>` +
      `<tr style="background:#f5f5f5;"><th style="padding:8px 12px;border:1px solid #ddd;text-align:left;">受信日時</th><td style="padding:8px 12px;border:1px solid #ddd;">${now.toLocaleString('ja-JP')}</td></tr>` +
      `</table>` +
      `<p><a href="https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}" style="background:#4285f4;color:#fff;padding:8px 16px;border-radius:4px;text-decoration:none;">📊 スプレッドシートで確認</a></p>` +
      `</div>`;
    GmailApp.sendEmail(NOTIFY_EMAIL, subject, plainBody, { htmlBody });

    return ContentService
      .createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    console.error('processContact error:', err);
    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, error: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function testSendEmail() {
  GmailApp.sendEmail(NOTIFY_EMAIL, '[PhysiqueLog] GAS接続テスト', 'テストメールです。');
  SpreadsheetApp.openById(SPREADSHEET_ID).toast('送信しました ✓', 'テスト', 5);
}
