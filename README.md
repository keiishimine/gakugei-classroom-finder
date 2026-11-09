# 学芸大 空き教室ナビ — 公式シラバス自動同期・試作版（2026年度）

東京学芸大学の**公開シラバスの個別ページを直接取得し、サイトの授業CSVをGitHub Actionsで定期更新する構成**を追加しました。大学公認ではありません。既知の11URLに限って自動更新し、検索画面からの**全科目自動発見は未完成**です。

## PCからアップロードする（2026年11月版）

1. ZIPをPCで展開します。**ZIPファイルをそのままアップロードしないでください。**
2. GitHub の `keiishimine/gakugei-classroom-finder` → `Code` → `uploading an existing file` （空のとき）または `Add file` → `Upload files` に進みます。
3. **展開フォルダの中身をすべて選択**し、ドラッグ＆ドロップします。`index.html` がリポジトリ直下に来るようにし、`.github/workflows/` も含めます。必要ならWindowsのエクスプローラーで Ctrl+A を使います。
4. `Commit changes` を押し `main` に反映します。
5. GitHub → `Settings` → `Pages` → `Build and deployment` → **Source: GitHub Actions** を選びます（この版では `Deploy from a branch` を選ばない）。
6. `Actions` → `Deploy classroom finder` → `Run workflow` でサイトを公開します。URLは `Settings` → `Pages` に表示されます。
7. シラバスの自動取得は **大学側の利用条件確認後だけ**、`Settings` → `Secrets and variables` → `Actions` → `Variables` で `SYLLABUS_AUTO_FETCH_ENABLED=true` にします。それまでは公式サイトに自動アクセスしません。

**公開初期の授業データは11件のみで全教室を網羅しません。** GitHub Actionsで更新された後は、`Sync public syllabus (known URLs)` ワークフロー内の `deploy` ジョブがPagesにも反映します。GitHubのボットが作るコミットでは通常のpushトリガーが起動しないため、この明示的なデプロイを入れています。

## 今回追加した自動同期の仕組み

```text
大学の公開シラバス個別ページ（既知11URL）
    │  利用条件確認済みのときのみ、3.5秒間隔で順番に取得
    ▼
GitHub Actions（日次 04:17頃 JST／手動実行も可能）
    │  11件すべて正常取得・解析、科目ID一致検査
    ▼
verified_2026_classes.csv / verified_2026_rooms.csv / sync_status.json
    │  差分があった場合のみコミット → その後Pagesへ明示的に再デプロイ
    ▼
学芸大 空き教室ナビ（サイト表示時に最新CSVをロード）
```

### 有効化の具体的な手順

1. ZIPを解凍して、`index.html`、`app.js`、`data/`、`scripts/`、`tests/` と、**隠しフォルダ `.github/workflows/`** をリポジトリ直下へアップロードしてください。ZIPそのものをGitHubへ置くのではなく中身を置きます。既存ファイルがあれば上書きします。
2. 大学の教務担当・情報担当部署に、**公開シラバスの機械的な定期取得・講義室／曜日時限／科目名の第三者公開**の可否、希望アクセス頻度、利用条件を確認してください。許可・規程に反するアクセスはしないでください。
3. GitHubの `[Settings] → [Secrets and variables] → [Actions] → [Variables] → [New repository variable]` で `SYLLABUS_AUTO_FETCH_ENABLED` を作り、条件確認後に `true` を設定してください。**このフラグがないうちは自動アクセスしません。**
4. GitHubの `[Actions] → [Sync public syllabus (known URLs)] → [Run workflow]` で手動テストします。`robots.txt` を確認できない・アクセス禁止・取得不可・解析不可のときは失敗し、古いCSVを残します。
5. 正常な場合は毎日04:17頃（日本時間）にGitHub Actionsが起動して、既知URLを確認します。GitHubのスケジュールは遅延・実行漏れがあります。`data/sync_status.json` と検索サイトの「最終取得」で日時を確認できます。
6. GitHub Pagesは `[Settings] → [Pages] → Source: GitHub Actions` で公開します。`Deploy classroom finder` が通常のコミットを、同期ワークフロー内の `deploy` ジョブが自動更新のコミットを公開します。必要に応じて `[Settings] → [Actions] → [General]` のWorkflow permissionsを確認します。ワークフローは `permissions: contents: write` を要求しています。

**GitHub連携は読み取り可能ですが、このチャットからリポジトリへの書き込みは403（Resource not accessible by integration）で拒否されていたため、作業ファイルはZIPで渡しています。**

### 新規授業を「自動発見」するには：検索フォームの調査が必要

個別URLを更新するだけでは、未知の科目・新設講義・全棟の全時間割を網羅できません。公式検索ページ

https://tgusyl.u-gakugei.ac.jp/ext_syllabus/syllabusSearchDirect.do?nologin=on

には「タイトル」「開講学期」「曜日・時限」などの項目がありますが、フォーム送信パラメータ、検索結果のページ送り、全件出力可能なAPI・公開データ提供の有無は未確認です。

- 利用条件を確認後、`[Actions] → [Inspect official syllabus search form (single page)] → [Run workflow]` を実行します。これは**公開検索ページを1件取得するだけ**で、検索送信も一括収集も行いません。
- 実行結果のArtifactsから `syllabus-search-form-metadata` をダウンロードすると、フォーム名・検索選択肢・スクリプト等を記した `search_form.json` が得られます（hidden input valuesやCookieは保存しません）。この情報を基に公式検索結果からの漏れない科目ID収集を実装できます。
- 公開の時間割一覧を大学側からCSV/API等で提供してもらえるなら、そちらの利用が優先です。検索画面スクレイピングに頼るより正確で、アクセス負荷も抑えられます。
- 対象年を2027年度に切り替える際は、年度フィルタ・既知URL一覧を更新する必要があります。

### 失敗時の安全設計

- URLは公式 `tgusyl.u-gakugei.ac.jp` の `referenceDirect.do` に固定。ログイン・subjectID推測・非公開API叩きはなし。
- `robots.txt` が未確認、許可がない、取得エラーがある場合は停止。タイムアウト、サイズ制限、低頻度アクセスを設定。
- 既知の11ページに失敗が1件でもある、解析結果が曖昧、IDが不一致の場合はCSVを保存しません。GitHub Actionsもその時点で失敗し、サイトには最後にコミットされたデータが残ります。
- 更新できても `coverage.csv` の `complete` は自動付与しません。**未掲載＝空きという誤判定を防止します。**
- 公開シラバスでは補講・臨時使用・施設予約・在室を判定できません。

### ファイルの構成（追加分）

```text
.github/workflows/sync-syllabus.yml      既知11URLの毎日自動チェック＆CSV差分コミット
.github/workflows/inspect-syllabus.yml   検索フォームのメタ情報を一度だけ調査（手動）
scripts/sync_public_syllabus.py          既知URLの整合性検査／原子的CSV更新
scripts/probe_syllabus_search.py         検索画面のフォーム情報だけを取得
data/sync_status.json                   最後の同期時刻・対象数・網羅性
```

ローカルの単体テスト：

```bash
python3 -m unittest discover -s tests -v
node --check app.js
```

---

東京学芸大学の**公開シラバスに掲載された通常授業の予定**を、曜日・時限・教室で確認する静的Webサイトです。スマートフォン対応、GitHub Pagesで公開可能。**大学公認のサービスではありません。**

## 今の完成状況（2026年11月8日）

- 2026年度の公式シラバス個別ページから、出典URL付きの **11科目・6教室** を確認して同梱しています。全科目・全教室の網羅性は確認できていません。
- 登録済みの授業がある時間帯は「授業予定あり」、それ以外は原則「要確認」です。**「未登録だから空き」という判定は行いません。**
- 画面の「架空のデモデータ」を選ぶと、完全に架空の時間割で「空き候補」の表示を試せます。
- **ブラウザからの大学サイトアクセスは行いません。** GitHub Actionsによる既知URLの直接取得に対応しました。全科目同期・リアルタイムの教室利用状況の把握は未実装です。
- `scripts/import_saved_syllabus.py` で、ブラウザで保存した2026年度シラバスのHTML/TXTから、授業CSVを**オフラインで**追加できます。
- `scripts/fetch_approved_syllabus_urls.py` と `scripts/sync_public_syllabus.py` は、大学側の利用条件確認後に使える定期取得の仕組みです。GitHub側のオプトイン設定がないうちは実行しません。

## まずGitHub Pagesで公開

1. このフォルダ内の `index.html`、`style.css`、`app.js`、`README.md`、`data/`、`scripts/`、`tests/`、`.nojekyll` を、GitHubリポジトリの**直下**にアップロード（ZIPを一つだけアップロードしてもサイトにはなりません）。
2. GitHubの **Settings → Pages → Build and deployment → Source: GitHub Actions** に設定し、Actions → Deploy classroom finder → Run workflow で公開します。
3. Pagesの表示するURLを開きます。通常、リポジトリ `keiishimine/gakugei-classroom-finder` であれば `https://keiishimine.github.io/gakugei-classroom-finder/` 形式ですが、**公開設定が完了していなければ使えません**。
4. 初期画面は **2026年度の部分データ（11件・6室）** です。「秋学期／月曜／2限」を選ぶと、`C401` に「日本国憲法」が表示されるはずです。他の教室は「要確認」です。

ローカルで試すには、リポジトリ直下で `python3 -m http.server 8000` を実行し、`http://localhost:8000/` を開きます。ブラウザで `index.html` を直接開くとCSV読込が制限されます。

## ファイル構成

```text
index.html                           検索画面
style.css                            デザイン（スマホ対応）
app.js                               照合・検証・CSV読み込み（ブラウザだけで動作）
data/verified_2026_rooms.csv        公式シラバスで確認した教室（部分リスト）
data/verified_2026_classes.csv      公式シラバス確認済みの11科目（部分リスト）
data/coverage.csv                    全件確認済みの時間帯（現在は空）
data/known_syllabus_urls.txt         確認済みの公式個別ページ11URL
data/rooms.csv                       架空デモ用の教室
data/classes.csv                       架空デモ用の授業
scripts/import_saved_syllabus.py     保存済みHTML/TXT→CSV（ネットアクセスなし）
scripts/fetch_approved_syllabus_urls.py 許可確認後のみ実行できる限定URL取得器
tests/test_syllabus_import.py        パーサーの単体テスト
```

## データの形式

`data/verified_2026_rooms.csv` または取り込み用の教室一覧CSV：

| room_id | building | floor | room_type |
|---|---|---|---|
| C401 | C | 4 | 公開シラバス掲載 |

`data/verified_2026_classes.csv` または取り込み用の授業一覧CSV：

| 列名 | 例 | 内容 |
|---|---|---|
| course_id | 241300000789 | 授業の識別子 |
| course_name | 日本国憲法 | 科目名 |
| term | fall | `spring` / `fall` |
| weekday | mon | `mon` / `tue` / `wed` / `thu` / `fri` |
| period_start | 2 | 1～6 |
| period_end | 2 | 同上。連続授業の場合は終了時限 |
| room_id | C401 | 教室一覧と一致させる |
| schedule_type | weekly | `weekly` / `irregular` |
| source_url | https://tgusyl.u-gakugei.ac.jp/... | 個別ページ |
| last_verified | 2026-11-08 | 調査日（更新日時ではない） |
| teacher | 宿谷 晃弘 | 任意 |

`data/coverage.csv`（任意：非常に重要）には次の列を用います。

```csv
term,weekday,period,building,status,source_url,verified_at
```

全教室一覧とその学期・曜日・時限の**対象授業が網羅的に確認済み**で、別途予約・補講等の限界を理解している枠だけ、例えば `fall,mon,2,C,complete,https://example.edu/official-full-timetable,2026-11-08` と記入します。**現在の `coverage.csv` はヘッダーのみで、全件照合済み枠はありません。** 適切な根拠がない状態で `complete` を設定しないでください。

判定ロジックは次の通り：

1. その時間帯に `weekly` 授業が登録済み → **授業予定あり**。
2. `irregular` の登録がある → **要確認**。
3. その建物・学期・曜日・時限が全件照合済みであることを coverage に明示 → **空き候補**（授業登録がない場合だけ）。
4. その他 → **要確認**。

`空き候補` は「通常授業予定の登録がない」ことを示すだけで、**現在の無人・利用許可・施設予約なしを保証しません**。教室一覧に登録されていない教室は検索結果に出ません。

## 新しい2026年度シラバスを追加する（まずオフライン方式）

1. 公開シラバスの詳細ページをブラウザで開き、HTML形式で保存します。サイトのデータ取得・再配布に関する大学の条件も確認してください。
2. できればファイル名を、URLの `subjectID` で指定してください（例：`241300000789.html`）。これにより出典URLが自動生成できます。URLがわからない場合は出典なしとして登録されます。
3. 保存したHTMLを `saved_syllabus` フォルダに入れ、リポジトリ直下で次を実行します：

```bash
python3 scripts/import_saved_syllabus.py saved_syllabus/*.html --dry-run
python3 scripts/import_saved_syllabus.py saved_syllabus/*.html
```

4. 変換が成功した授業は、`data/verified_2026_classes.csv` と `data/verified_2026_rooms.csv` に重複除去して追記されます。これら2ファイルをGitHubに反映します。
5. 変則授業、日程不明、教室が「別途指示」の授業は自動登録を**見送ります**。標準授業以外のコマも正確に扱うには、日付ベースのデータモデル拡張が必要です。

初回に試す場合のテスト：

```bash
python3 -m unittest discover -s tests -v
node --check app.js
```

## 任意：許可が取れた場合の限定的な自動取得

大学側の**自動取得と再利用・公開の条件を確認し、許可された場合だけ**、用意した公開URLリストを小規模にダウンロードできます。リストには新たなURLを必要な分だけ追記できます。

```bash
python3 scripts/fetch_approved_syllabus_urls.py --permission-confirmed
python3 scripts/import_saved_syllabus.py saved_syllabus/*.html
```

- 必ず `robots.txt` を検査します。許可を確認できなければ停止します。
- ダウンロード対象は `nologin=on` の公式個別シラバスURLだけです（検索結果の網羅的巡回は実装していません）。
- 1回につき25URL以下、最低3秒間隔です。大学システム側の制約がより厳しい場合は従ってください。
- ログイン・認証回避・制限回避はしません。
- この限定URL方式では、**シラバス全件を自動収集できません**。本当に空き候補を探すには、公式の時間割全件提供または許可されたエクスポートが必要です。

## 調べてわかったこと

公開の公式検索フォーム：

https://tgusyl.u-gakugei.ac.jp/ext_syllabus/syllabusSearchDirect.do?nologin=on

公式個別シラバスの例（秋学期・月曜2限・C401）：

https://tgusyl.u-gakugei.ac.jp/ext_syllabus/referenceDirect.do?formatCD=1&nologin=on&subjectID=241300000789

大学ICTセンターには教室時間割に関する過去のページもありますが、過去の掲載情報を2026年度の全教室の利用可否として流用してはいけません。教室の空きと使用許可は別です。

## 未対応・留意点

- 公式サイトのAPI / 検索フォームからの**全件自動収集**、学内ポータルとの同期（既知11URLの直接更新は実装済み）
- 授業日と通常の曜日が一致しない日、祝日、補講、休講、隔週、集中講義、教室変更
- 施設利用予約、ICTセンター管理室、ゼミの非公開利用、実際の在室確認
- 大学からの許可確認と著作権・データ利用条件の確認

大学に問い合わせる際は、「公開シラバスの講義室・学期・曜日時限を取得して、通常授業の予定を検索できる非公式サイトに利用したい。授業データのCSV出力や一括提供の可否、機械的アクセス・再配布の条件、教室利用情報の更新方法」を確認するとよいでしょう。
