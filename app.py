"""
シフト管理アプリ - メイン画面
"""
import calendar
import os
from datetime import date

import pandas as pd
import streamlit as st

import db
from excel_export import export_to_excel
from scheduler import ROLES, generate_shift

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]
FIXED_DAYS = {"店長": 22, "マネージャー": 22, "ロングパート": 22, "ショートパート": 16}

st.set_page_config(page_title="シフト管理", layout="wide")


# =============================================================================
# ログイン画面
# =============================================================================

def show_login():
    st.title("シフト管理アプリ")
    tab_login, tab_signup = st.tabs(["ログイン", "新規登録"])

    with tab_login:
        with st.form("login_form"):
            code = st.text_input("会社コード")
            password = st.text_input("パスワード", type="password")
            submitted = st.form_submit_button("ログイン", use_container_width=True)
            if submitted:
                company = db.authenticate_company(code, password)
                if company:
                    st.session_state.company = company
                    st.session_state.company_id = company["id"]
                    st.rerun()
                else:
                    st.error("会社コードまたはパスワードが正しくありません")

    with tab_signup:
        st.caption("はじめてご利用の方は新規登録してください")
        with st.form("signup_form"):
            new_name = st.text_input("会社名・店舗名")
            new_code = st.text_input("会社コード（ログイン時に使用）")
            new_pass = st.text_input("パスワード", type="password")
            new_pass2 = st.text_input("パスワード（確認）", type="password")
            submitted = st.form_submit_button("登録する", use_container_width=True)
            if submitted:
                if not new_name or not new_code or not new_pass:
                    st.error("すべての項目を入力してください")
                elif new_pass != new_pass2:
                    st.error("パスワードが一致しません")
                elif len(new_pass) < 8:
                    st.error("パスワードは8文字以上にしてください")
                else:
                    company = db.register_company(new_code, new_name, new_pass)
                    if company:
                        st.session_state.company = company
                        st.session_state.company_id = company["id"]
                        st.success("登録完了！ログインしました")
                        st.rerun()
                    else:
                        st.error("この会社コードはすでに使われています")


if "company" not in st.session_state:
    show_login()
    st.stop()


# =============================================================================
# ログイン済み — セッション初期化
# =============================================================================

company_id = st.session_state.company_id
company_name = st.session_state.company["name"]

if "employees" not in st.session_state:
    st.session_state.employees = db.load_employees(company_id)

if "shift_result" not in st.session_state:
    st.session_state.shift_result = None

if "shift_year" not in st.session_state:
    st.session_state.shift_year = date.today().year

if "shift_month" not in st.session_state:
    st.session_state.shift_month = date.today().month


# =============================================================================
# サイドバー
# =============================================================================

with st.sidebar:
    st.caption(f"ログイン中：{company_name}")
    page = st.radio("メニュー", ["📋 従業員マスタ", "📅 シフト作成", "📊 結果確認・編集"])
    st.divider()
    if st.button("ログアウト", use_container_width=True):
        for key in ["company", "company_id", "employees", "shift_result", "shift_year", "shift_month"]:
            st.session_state.pop(key, None)
        st.rerun()


# =============================================================================
# ページ1: 従業員マスタ
# =============================================================================

if page == "📋 従業員マスタ":
    st.title("従業員マスタ設定")
    st.caption("従業員の基本情報と希望を登録します（初回のみ・後から編集可）")

    employees = st.session_state.employees

    with st.expander("＋ 従業員を追加", expanded=len(employees) == 0):
        new_role = st.selectbox("ロール", ROLES, key="new_role_select")
        fixed_days = FIXED_DAYS.get(new_role)

        with st.form("add_employee"):
            new_name = st.text_input("名前")

            st.write("希望休み曜日（複数選択可）")
            cols = st.columns(7)
            preferred_off = []
            for i, wd in enumerate(WEEKDAY_JP):
                if cols[i].checkbox(wd, key=f"new_off_{i}"):
                    preferred_off.append(i)

            if fixed_days:
                st.info(f"勤務日数：{fixed_days}日（{new_role}は固定）")
                new_max = fixed_days
            else:
                new_max = st.number_input("月の勤務日数", min_value=1, max_value=31, value=17)
            new_note = st.text_area("備考（自由記入）", height=68)

            submitted = st.form_submit_button("追加")
            if submitted:
                if not new_name:
                    st.error("名前を入力してください")
                elif any(e["name"] == new_name for e in employees):
                    st.error("同じ名前の従業員が既に存在します")
                else:
                    new_emp = {
                        "name": new_name,
                        "role": new_role,
                        "preferred_days_off": preferred_off,
                        "max_days": new_max,
                        "min_days": new_max,
                        "note": new_note,
                    }
                    saved = db.save_employee(company_id, new_emp)
                    st.session_state.employees = db.load_employees(company_id)
                    st.success(f"{new_name} を追加しました")
                    st.rerun()

    if not employees:
        st.info("まだ従業員が登録されていません")
    else:
        st.subheader(f"登録済み従業員（{len(employees)}人）")
        for idx, e in enumerate(employees):
            with st.expander(f"【{e['role']}】{e['name']}"):
                edit_role = st.selectbox("ロール", ROLES, index=ROLES.index(e["role"]), key=f"edit_role_{idx}")
                edit_fixed_days = FIXED_DAYS.get(edit_role)

                with st.form(f"edit_{idx}"):
                    edit_name = st.text_input("名前", value=e["name"])

                    st.write("希望休み曜日")
                    cols = st.columns(7)
                    edit_off = []
                    for i, wd in enumerate(WEEKDAY_JP):
                        if cols[i].checkbox(wd, value=(i in e.get("preferred_days_off", [])), key=f"edit_off_{idx}_{i}"):
                            edit_off.append(i)

                    if edit_fixed_days:
                        st.info(f"勤務日数：{edit_fixed_days}日（{edit_role}は固定）")
                        edit_max = edit_fixed_days
                    else:
                        edit_max = st.number_input(
                            "月の勤務日数",
                            min_value=1, max_value=31,
                            value=e.get("max_days", 17),
                            key=f"max_{idx}"
                        )
                    edit_note = st.text_area("備考", value=e.get("note", ""), height=68, key=f"note_{idx}")

                    col_save, col_del = st.columns(2)
                    saved = col_save.form_submit_button("💾 保存")
                    deleted = col_del.form_submit_button("🗑 削除", type="secondary")

                    if saved:
                        updated = {
                            "name": edit_name,
                            "role": edit_role,
                            "preferred_days_off": edit_off,
                            "max_days": edit_max,
                            "min_days": edit_max,
                            "note": edit_note,
                        }
                        db.update_employee(e["id"], updated)
                        st.session_state.employees = db.load_employees(company_id)
                        st.success("保存しました")
                        st.rerun()

                    if deleted:
                        db.delete_employee(e["id"])
                        st.session_state.employees = db.load_employees(company_id)
                        st.success("削除しました")
                        st.rerun()


# =============================================================================
# ページ2: シフト作成
# =============================================================================

elif page == "📅 シフト作成":
    st.title("月次シフト作成")

    employees = st.session_state.employees
    if not employees:
        st.warning("先に「従業員マスタ」で従業員を登録してください")
        st.stop()

    col1, col2 = st.columns(2)
    year = col1.number_input("年", min_value=2024, max_value=2030, value=st.session_state.shift_year)
    month = col2.number_input("月", min_value=1, max_value=12, value=st.session_state.shift_month)

    st.session_state.shift_year = year
    st.session_state.shift_month = month

    num_days = calendar.monthrange(year, month)[1]
    days = list(range(1, num_days + 1))

    st.subheader("今月の個別希望入力")
    st.caption("各従業員の希望を入力してください。入力がない日は自動で調整されます。")

    REQUEST_OPTIONS = ["（指定なし）", "休み希望", "出勤希望"]

    monthly_requests = {}
    for e in employees:
        name = e["name"]
        with st.expander(f"【{e['role']}】{name}"):
            reqs = {}
            cols_per_row = 7
            day_chunks = [days[i:i+cols_per_row] for i in range(0, len(days), cols_per_row)]
            for chunk in day_chunks:
                cols = st.columns(len(chunk))
                for col, d in zip(cols, chunk):
                    weekday = calendar.weekday(year, month, d)
                    label = f"{d}({WEEKDAY_JP[weekday]})"
                    val = col.selectbox(label, REQUEST_OPTIONS, key=f"req_{name}_{d}", label_visibility="visible")
                    if val != "（指定なし）":
                        reqs[d] = val
            monthly_requests[name] = reqs

    st.divider()
    if st.button("🚀 シフトを自動生成する", type="primary", use_container_width=True):
        with st.spinner("シフトを計算中...（数秒かかります）"):
            result = generate_shift(int(year), int(month), employees, monthly_requests)

        status = result.pop("status", "")
        if status in ("Optimal", "Feasible"):
            st.session_state.shift_result = result
            st.session_state.shift_year = int(year)
            st.session_state.shift_month = int(month)
            st.success("シフトを生成しました！「結果確認・編集」画面で確認してください")
        else:
            st.error(f"シフトの生成に失敗しました（status: {status}）。希望を一部緩和してください。")


# =============================================================================
# ページ3: 結果確認・編集
# =============================================================================

elif page == "📊 結果確認・編集":
    st.title("シフト確認・微調整")

    if st.session_state.shift_result is None:
        st.info("まだシフトが生成されていません。「シフト作成」画面から生成してください。")
        st.stop()

    year = st.session_state.shift_year
    month = st.session_state.shift_month
    employees = st.session_state.employees
    result = st.session_state.shift_result

    num_days = calendar.monthrange(year, month)[1]
    days = list(range(1, num_days + 1))

    st.subheader(f"{year}年{month}月 シフト表")

    ROLE_ORDER = ["店長", "マネージャー", "ロングパート", "ショートパート", "アルバイト"]
    sorted_employees = sorted(employees, key=lambda e: ROLE_ORDER.index(e["role"]) if e["role"] in ROLE_ORDER else 99)

    col_labels = []
    for d in days:
        wd = calendar.weekday(year, month, d)
        col_labels.append(f"{d}\n{WEEKDAY_JP[wd]}")

    rows = []
    for e in sorted_employees:
        name = e["name"]
        row = {"ロール": e["role"], "名前": name}
        work_count = 0
        for d in days:
            wd = calendar.weekday(year, month, d)
            label = f"{d}\n{WEEKDAY_JP[wd]}"
            is_work = result.get(name, {}).get(d, False)
            row[label] = "○" if is_work else "×"
            if is_work:
                work_count += 1
        row["勤務日数"] = work_count
        rows.append(row)

    df = pd.DataFrame(rows)

    st.caption("セルを変更してシフトを微調整できます")
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        disabled=["ロール", "名前", "勤務日数"],
        column_config={
            col: st.column_config.SelectboxColumn(col, options=["○", "×"], width="small")
            for col in col_labels
        }
    )

    if st.button("💾 変更を反映する"):
        new_result = {}
        for _, row in edited_df.iterrows():
            name = row["名前"]
            new_result[name] = {}
            for d in days:
                wd = calendar.weekday(year, month, d)
                label = f"{d}\n{WEEKDAY_JP[wd]}"
                new_result[name][d] = row[label] == "○"
        st.session_state.shift_result = new_result
        st.success("変更を反映しました")
        st.rerun()

    st.divider()

    if st.button("📥 Excelでダウンロード", type="primary"):
        filepath = export_to_excel(year, month, sorted_employees, st.session_state.shift_result, OUTPUT_DIR)
        with open(filepath, "rb") as f:
            st.download_button(
                label="⬇ ダウンロード",
                data=f,
                file_name=os.path.basename(filepath),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        st.success(f"Excelファイルを出力しました")

    st.divider()
    st.subheader("集計")
    summary_rows = []
    for e in sorted_employees:
        name = e["name"]
        work_days = sum(1 for d in days if result.get(name, {}).get(d, False))
        rest_days = num_days - work_days
        summary_rows.append({"ロール": e["role"], "名前": name, "勤務日数": work_days, "休み日数": rest_days})
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
