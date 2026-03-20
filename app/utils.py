r"""D:\MyActivity\MyInfoBusiness\MyPythonApps\10 Typical_infrastructure\app\utils.py"""

from __future__ import annotations

from secrets import token_urlsafe
from uuid import uuid4

import bcrypt


def new_id32() -> str:
    return uuid4().hex


def hash_password(plain: str) -> str:
    pw = plain.encode("utf-8")
    if len(pw) > 72:
        pw = pw[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("ascii")


def generate_temp_password() -> str:
    return token_urlsafe(12)

