"""
Supabase接続・DB操作
"""
import os
import bcrypt
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_client():
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client


# ---- 会社認証 ----

def authenticate_company(code: str, password: str) -> dict | None:
    """会社コードとパスワードで認証。成功したら会社情報を返す。"""
    sb = get_client()
    res = sb.table("companies").select("*").eq("code", code).execute()
    if not res.data:
        return None
    company = res.data[0]
    if bcrypt.checkpw(password.encode(), company["password_hash"].encode()):
        return company
    return None


# ---- 従業員 ----

def load_employees(company_id: str) -> list:
    sb = get_client()
    res = sb.table("employees").select("*").eq("company_id", company_id).order("created_at").execute()
    return res.data or []


def save_employee(company_id: str, employee: dict) -> dict:
    sb = get_client()
    record = {
        "company_id": company_id,
        "name": employee["name"],
        "role": employee["role"],
        "preferred_days_off": employee.get("preferred_days_off", []),
        "max_days": employee["max_days"],
        "min_days": employee["min_days"],
        "note": employee.get("note", ""),
    }
    res = sb.table("employees").insert(record).execute()
    return res.data[0]


def update_employee(employee_id: str, employee: dict):
    sb = get_client()
    record = {
        "name": employee["name"],
        "role": employee["role"],
        "preferred_days_off": employee.get("preferred_days_off", []),
        "max_days": employee["max_days"],
        "min_days": employee["min_days"],
        "note": employee.get("note", ""),
    }
    sb.table("employees").update(record).eq("id", employee_id).execute()


def delete_employee(employee_id: str):
    sb = get_client()
    sb.table("employees").delete().eq("id", employee_id).execute()
