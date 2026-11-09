/*
 * 東京学芸大学・空き教室ナビ 2026β
 * 公式シラバスの登録済み「一部」に授業がなければ原則「要確認」。
 * 例外: 利用者が全件照合済みと明示した時間帯か、架空のデモモードだけ「空き候補」。
 * サイトから大学システムへ自動でアクセスすることはありません。
 */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const fields = { term: $("term"), weekday: $("weekday"), period: $("period"), building: $("building"), keyword: $("keyword"), status: $("status") };
  const labels = { mon: "月曜", tue: "火曜", wed: "水曜", thu: "木曜", fri: "金曜" };
  const text = (element, value) => { element.textContent = String(value); };
  const datasets = {};
  let syncInfo = null;
  let active = { mode: "official", rooms: [], classes: [], coverage: [] };
  const sourceFiles = {
    official: ["data/verified_2026_rooms.csv", "data/verified_2026_classes.csv", "data/coverage.csv"],
    demo: ["data/rooms.csv", "data/classes.csv", null]
  };

  function parseCSV(input) {
    const str = String(input).replace(/^\uFEFF/, "");
    const records = [];
    let row = [], value = "", quoted = false;
    for (let i = 0; i < str.length; i++) {
      const c = str[i];
      if (quoted) {
        if (c === '"' && str[i + 1] === '"') { value += '"'; i++; }
        else if (c === '"') quoted = false;
        else value += c;
      } else if (c === '"' && !value) quoted = true;
      else if (c === ',') { row.push(value); value = ""; }
      else if (c === '\n' || c === '\r') {
        if (c === '\r' && str[i + 1] === '\n') i++;
        row.push(value); value = "";
        if (row.some(x => x.trim())) records.push(row);
        row = [];
      } else value += c;
    }
    if (quoted) throw new Error("CSVの引用符が閉じられていません。");
    row.push(value);
    if (row.some(x => x.trim())) records.push(row);
    if (!records.length) return [];
    const headers = records.shift().map(x => x.trim());
    if (new Set(headers).size !== headers.length) throw new Error("CSVのヘッダーが重複しています。");
    return records.map((values, i) => {
      if (values.length !== headers.length) throw new Error(`CSV ${i + 2}行目で列数が一致しません。`);
      return Object.fromEntries(headers.map((name, index) => [name, values[index].trim()]));
    });
  }
  function validateRooms(rows) {
    if (!rows.length) throw new Error("教室一覧が空です。");
    const seen = new Set();
    return rows.map((r, i) => {
      const room_id = (r.room_id ?? "").normalize("NFKC").replace(/\s+/g, "").toUpperCase();
      const building = (r.building ?? "").normalize("NFKC").toUpperCase();
      if (!room_id || !building) throw new Error(`教室一覧${i + 2}行目: room_id と building が必要です。`);
      if (seen.has(room_id)) throw new Error(`教室一覧: ${room_id} が重複しています。`);
      seen.add(room_id);
      return { ...r, room_id, building };
    });
  }
  function validateClasses(rows, rooms) {
    const known = new Set(rooms.map(x => x.room_id));
    return rows.map((r, i) => {
      const at = `授業一覧${i + 2}行目`;
      const room_id = (r.room_id ?? "").normalize("NFKC").replace(/\s+/g, "").toUpperCase();
      const start = Number(r.period_start), end = Number(r.period_end);
      if (!r.course_name || !room_id) throw new Error(`${at}: course_name と room_id が必要です。`);
      if (!known.has(room_id)) throw new Error(`${at}: 教室 ${room_id} は教室一覧にありません。`);
      if (!["spring", "fall"].includes(r.term)) throw new Error(`${at}: term は spring/fall のどちらかです。`);
      if (!Object.hasOwn(labels, r.weekday)) throw new Error(`${at}: weekday が不正です。`);
      if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end > 6 || start > end) throw new Error(`${at}: 時限は1～6の整数で入力してください。`);
      if (!["weekly", "irregular"].includes(r.schedule_type)) throw new Error(`${at}: schedule_type は weekly/irregular です。`);
      return { ...r, room_id, period_start: start, period_end: end };
    });
  }
  function validateCoverage(rows) {
    const seen = new Set();
    return rows.map((r, i) => {
      const at = `全件確認CSV${i + 2}行目`;
      const p = Number(r.period), b = (r.building ?? "").normalize("NFKC").toUpperCase();
      if (!["spring", "fall"].includes(r.term) || !Object.hasOwn(labels, r.weekday) || !Number.isInteger(p) || p < 1 || p > 6 || !b) throw new Error(`${at}: 学期・曜日・時限・建物が不正です。`);
      if (r.status !== "complete" || !r.source_url || !r.verified_at) throw new Error(`${at}: 全件確認済みとして認めるには complete・source_url・verified_at が必須です。`);
      const key = `${r.term}|${r.weekday}|${p}|${b}`;
      if (seen.has(key)) throw new Error(`${at}: 時間帯が重複しています。`);
      seen.add(key);
      return { ...r, period: p, building: b };
    });
  }
  function isComplete(term, weekday, period, building) {
    if (active.mode === "demo") return true; // only the simulated timetable
    return active.coverage.some(c => c.term === term && c.weekday === weekday && c.period === period && c.building === building && c.status === "complete");
  }
  function statusOf(room, term, weekday, period) {
    const matches = active.classes.filter(c => c.room_id === room.room_id && c.term === term && c.weekday === weekday && c.period_start <= period && c.period_end >= period);
    const weekly = matches.filter(c => c.schedule_type === "weekly");
    if (weekly.length) return { status: "busy", matches: weekly };
    if (matches.length) return { status: "unknown", matches };
    return { status: isComplete(term, weekday, period, room.building) ? "free" : "unknown", matches: [] };
  }
  function safeURL(raw) {
    try { const url = new URL(raw); return ["https:", "http:"].includes(url.protocol) ? url.toString() : null; }
    catch { return null; }
  }
  function createCard(room, info) {
    const card = document.createElement("article"); card.className = `room-card ${info.status}`;
    const top = document.createElement("div"); top.className = "room-top";
    const title = document.createElement("div");
    const name = document.createElement("div"); name.className = "room-name"; text(name, room.room_id);
    const b = document.createElement("span"); b.className = "room-building"; text(b, `${room.building}棟${room.floor ? ` · ${room.floor}階` : ""}`);
    title.append(name, b);
    const pill = document.createElement("span"); pill.className = `status-pill ${info.status}`;
    text(pill, { free: "空き候補", busy: "授業予定あり", unknown: "要確認" }[info.status]);
    top.append(title, pill);
    const detail = document.createElement("div"); detail.className = "room-detail";
    if (info.status === "free") text(detail, active.mode === "demo" ? "架空データ上、授業予定なし" : "登録対象の時間割を全件照合済み（実際の利用可否とは別）");
    else if (!info.matches.length) text(detail, "この時間帯の全授業を確認できていません");
    else {
      const c = info.matches[0];
      text(detail, info.status === "unknown" ? `特殊日程：${c.course_name}` : `${c.course_name}${c.teacher ? `／${c.teacher}` : ""}${info.matches.length > 1 ? ` ほか${info.matches.length - 1}件` : ""}`);
      const url = safeURL(c.source_url);
      if (url) { const a = document.createElement("a"); a.href = url; a.target = "_blank"; a.rel = "noopener noreferrer"; text(a, "出典を開く ↗"); detail.append(a); }
    }
    card.append(top, detail);
    return card;
  }
  function formatSyncTime() {
    if (!syncInfo || syncInfo.status !== "ok" || !syncInfo.updated_at) return "自動同期：未実行";
    const date = new Date(syncInfo.updated_at);
    if (Number.isNaN(date.getTime())) return "自動同期：日時を確認できません";
    return `最終取得：${date.toLocaleString("ja-JP", { timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}（日本時間）`;
  }
  function infoText() {
    if (active.mode === "official") return `2026年度シラバス確認済み ${active.classes.length}科目・${active.rooms.length}教室（部分データ）／${formatSyncTime()}`;
    if (active.mode === "demo") return `架空の授業 ${active.classes.length}件・${active.rooms.length}室`;
    return `持込CSV ${active.classes.length}件・${active.rooms.length}室／全件確認枠 ${active.coverage.length}件`;
  }
  function render() {
    const term = fields.term.value, weekday = fields.weekday.value, period = Number(fields.period.value);
    const building = fields.building.value, keyword = fields.keyword.value.trim().normalize("NFKC").toLowerCase(), status = fields.status.value;
    text($("conditions"), `${term === "fall" ? "秋学期" : "春学期"}・${labels[weekday]}${period}限`);
    const all = active.rooms.filter(r => (building === "all" || r.building === building) && r.room_id.toLowerCase().includes(keyword)).map(room => ({ room, ...statusOf(room, term, weekday, period) }));
    const counts = { free: 0, busy: 0, unknown: 0 };
    all.forEach(r => counts[r.status]++);
    for (const kind of ["free", "busy", "unknown"]) text($(`${kind}-count`), counts[kind]);
    const shown = all.filter(r => status === "all" || r.status === status).sort((a,b) => a.room.room_id.localeCompare(b.room.room_id,"ja"));
    text($("results-summary"), `${shown.length}室を表示（検索対象 ${all.length}室）`);
    text($("data-message"), infoText());
    const list = $("room-list"); list.replaceChildren();
    if (!shown.length) {
      const empty = document.createElement("p"); empty.className = "empty";
      text(empty, !all.length ? "この条件では教室一覧に該当する教室が登録されていません。未登録＝空きではありません。" : "表示条件に一致する教室はありません。");
      list.append(empty);
    } else shown.forEach(x => list.append(createCard(x.room, x)));
  }
  function applyDataset(which) {
    if (!datasets[which]) throw new Error(`${which}のデータを読み込めませんでした。`);
    active = { mode: which, ...datasets[which] };
    const demo = which === "demo";
    text($("dataset-pill"), demo ? "DEMO DATA" : "2026 PARTIAL");
    text($("sync-stamp"), demo ? "デモデータを表示中" : `${formatSyncTime()} ／ 取得先：大学の公開シラバス（既知URLのみ）`);
    text($("notice-title"), demo ? "以下は架空のデモデータです。" : "2026年度シラバスを一部のみ反映しています。");
    text($("notice-body"), demo ? "画面の操作を試すための架空データです。検索結果を実際の教室利用判断に使わないでください。" : `公開シラバスで確認できた${active.classes.length}科目・${active.rooms.length}教室のみを登録。全体の時間割は網羅していないため、授業が表示されない教室も「要確認」です。`);
    render();
  }
  function updateImportButton() { $("apply-csv").disabled = !($("rooms-file").files.length && $("classes-file").files.length); }
  for (const field of Object.values(fields)) field.addEventListener("input", render);
  $("dataset").addEventListener("change", () => {
    const value = $("dataset").value;
    if (value === "custom") return;
    try { applyDataset(value); } catch(e) { text($("import-message"), e.message); }
  });
  for (const id of ["rooms-file", "classes-file", "coverage-file"]) {
    $(id).addEventListener("change", () => {
      text($(`${id}-name`), $(id).files[0]?.name ?? (id === "coverage-file" ? "未選択：すべて要確認扱い" : "未選択"));
      updateImportButton();
    });
  }
  $("apply-csv").addEventListener("click", async () => {
    $("apply-csv").disabled = true;
    try {
      const [roomText, classText, coverageText] = await Promise.all([
        $("rooms-file").files[0].text(),
        $("classes-file").files[0].text(),
        $("coverage-file").files[0]?.text() ?? Promise.resolve("")
      ]);
      const rooms = validateRooms(parseCSV(roomText));
      const classes = validateClasses(parseCSV(classText), rooms);
      const coverage = validateCoverage(parseCSV(coverageText));
      active = { mode: "custom", rooms, classes, coverage };
      if (!$('dataset').querySelector('option[value="custom"]')) {
        const option = document.createElement("option"); option.value = "custom"; text(option, "読み込んだCSV"); $("dataset").append(option);
      }
      $("dataset").value = "custom";
      text($("dataset-pill"), "CUSTOM CSV");
      text($("notice-title"), "読み込んだCSVの内容を表示中です。");
      text($("notice-body"), coverage.length ? `全件確認枠${coverage.length}件のみ「空き候補」を出します。それ以外は「要確認」です。` : "時間帯別の全件確認ファイルがないため、登録済みの授業だけ「授業予定あり」と表示します。");
      text($("import-message"), `${classes.length}件の授業データを反映しました。`);
      render();
    } catch(e) { text($("import-message"), `CSVの読み込みエラー：${e.message}`); }
    updateImportButton();
  });
  $("reset-default").addEventListener("click", () => {
    $("dataset").value = "official";
    text($("import-message"), "2026年度の確認済み部分データに戻しました。");
    applyDataset("official");
  });
  async function fetchCSV(path) {
    const response = await fetch(path, { cache: "no-store" });
    if (!response.ok) throw new Error(`${path}（HTTP ${response.status}）を読み込めません。`);
    return parseCSV(await response.text());
  }
  async function loadDataset(mode) {
    const [roomPath, classPath, coveragePath] = sourceFiles[mode];
    const [r, c, v] = await Promise.all([fetchCSV(roomPath), fetchCSV(classPath), coveragePath ? fetchCSV(coveragePath) : Promise.resolve([])]);
    const rooms = validateRooms(r);
    return { rooms, classes: validateClasses(c, rooms), coverage: validateCoverage(v) };
  }
  async function main() {
    try {
      const [official, demo, status] = await Promise.all([
        loadDataset("official"), loadDataset("demo"),
        fetch("data/sync_status.json", { cache: "no-store" })
          .then(r => r.ok ? r.json() : null).catch(() => null)
      ]);
      syncInfo = status;
      datasets.official = official; datasets.demo = demo;
      applyDataset("official");
    } catch(e) {
      text($("results-summary"), `データ読み込みに失敗しました：${e.message}`);
      text($("data-message"), "GitHub PagesなどのHTTPサーバー上で開いてください。");
    }
  }
  main();
})();
