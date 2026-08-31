"""全部 ORM 模型。alembic/env.py 依赖本包导入即注册全部表。"""
from app.models.calc import *  # noqa: F401,F403
from app.models.config_domain import *  # noqa: F401,F403
from app.models.equipment import *  # noqa: F401,F403
from app.models.project import *  # noqa: F401,F403
