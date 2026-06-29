"""
シフト自動生成ロジック
PuLPを使って制約条件を満たす最適なシフトを計算する
"""
import calendar
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpBinary, LpStatus, value, PULP_CBC_CMD


ROLES = ["店長", "マネージャー", "ロングパート", "ショートパート", "アルバイト"]

# ロールごとの1日の最低必要人数（デフォルト値・変更可能）
DEFAULT_MIN_STAFF = {
    "店長": 1,
    "マネージャー": 1,
    "ロングパート": 1,
    "ショートパート": 0,
    "アルバイト": 0,
}

# 週あたりの最大勤務日数
MAX_WORK_DAYS_PER_WEEK = {
    "店長": 5,
    "マネージャー": 5,
    "ロングパート": 5,
    "ショートパート": 4,
    "アルバイト": 4,
}

# 月あたりの目標勤務日数（最小・最大）
MIN_WORK_DAYS_PER_MONTH = {
    "店長": 22,
    "マネージャー": 22,
    "ロングパート": 22,
    "ショートパート": 16,
    "アルバイト": 17,
}
MAX_WORK_DAYS_PER_MONTH = {
    "店長": 22,
    "マネージャー": 22,
    "ロングパート": 22,
    "ショートパート": 16,
    "アルバイト": 18,
}


def generate_shift(year: int, month: int, employees: list, monthly_requests: dict) -> dict:
    """
    シフトを生成して返す。

    Parameters
    ----------
    year : int
    month : int
    employees : list of dict
        [{"name": str, "role": str, "preferred_days_off": [0-6], "max_days": int}, ...]
    monthly_requests : dict
        {employee_name: {date: "休み" | "出勤希望" | "午前希望" | "午後希望"}, ...}

    Returns
    -------
    dict
        {employee_name: {date: bool}} True=出勤 False=休み
        + "status": "optimal" | "infeasible" | "feasible"
    """
    num_days = calendar.monthrange(year, month)[1]
    days = list(range(1, num_days + 1))
    emp_names = [e["name"] for e in employees]

    prob = LpProblem("ShiftScheduling", LpMinimize)

    # 決定変数: x[name][day] = 1 なら出勤
    x = {
        name: {day: LpVariable(f"x_{name}_{day}", cat=LpBinary) for day in days}
        for name in emp_names
    }

    # ---- 制約 ----

    emp_by_name = {e["name"]: e for e in employees}

    for e in employees:
        name = e["name"]
        role = e["role"]
        max_days = e.get("max_days") or MAX_WORK_DAYS_PER_MONTH.get(role, 18)
        preferred_off = e.get("preferred_days_off", [])  # 0=月, 6=日

        # 月の最大・最小勤務日数
        min_days = e.get("min_days") or MIN_WORK_DAYS_PER_MONTH.get(role, 10)
        # 月の日数を超えないよう上限を調整
        min_days = min(min_days, num_days)
        max_days = min(max_days, num_days)
        prob += lpSum(x[name][d] for d in days) >= min_days
        prob += lpSum(x[name][d] for d in days) <= max_days

        # 個別希望（月次リクエスト）
        requests = monthly_requests.get(name, {})
        for day, req in requests.items():
            if req == "休み希望":
                prob += x[name][day] == 0
            elif req == "出勤希望":
                prob += x[name][day] == 1

        # 希望休み曜日はなるべく休ませる（ソフト制約として扱うため強制しない）
        # 連続勤務は最大6日まで
        for d in days[:-6]:
            prob += lpSum(x[name][dd] for dd in range(d, d + 7)) <= 6

    # 各日: 店長・マネージャーのうち最低1人が出勤（2人以上いれば2人）
    senior_names = [e["name"] for e in employees if e["role"] in ("店長", "マネージャー")]
    min_seniors = min(len(senior_names), 2) if len(senior_names) >= 2 else min(len(senior_names), 1)
    for d in days:
        if senior_names:
            prob += lpSum(x[name][d] for name in senior_names) >= min_seniors

    # 各日の最低出勤人数（従業員数の約半数、最低1人）
    min_daily = max(1, min(3, len(emp_names) // 2))
    for d in days:
        prob += lpSum(x[name][d] for name in emp_names) >= min_daily

    # ---- 目的関数: 希望休み曜日に出勤させる回数を最小化 ----
    penalty_terms = []
    for e in employees:
        name = e["name"]
        preferred_off = e.get("preferred_days_off", [])
        for d in days:
            weekday = calendar.weekday(year, month, d)
            if weekday in preferred_off:
                penalty_terms.append(x[name][d])

    prob += lpSum(penalty_terms) if penalty_terms else 0

    # ---- 求解 ----
    prob.solve(PULP_CBC_CMD(msg=0))

    status = LpStatus[prob.status]

    result = {"status": status}
    for name in emp_names:
        result[name] = {}
        for d in days:
            result[name][d] = bool(value(x[name][d]) == 1)

    return result
