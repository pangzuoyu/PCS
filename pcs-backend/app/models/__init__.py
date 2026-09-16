"""全部 ORM 模型。alembic/env.py 依赖本包导入即注册全部表。"""
from app.models.calc import *  # noqa: F401,F403
from app.models.config_domain import *  # noqa: F401,F403
from app.models.deliverable import *  # noqa: F401,F403
from app.models.equipment import *  # noqa: F401,F403
from app.models.htri_template import *  # noqa: F401,F403
from app.models.pipe_code_template import *  # noqa: F401,F403
from app.models.project import *  # noqa: F401,F403
from app.models.project_template_pipe_class import *  # noqa: F401,F403
from app.models.psv_standards import *  # noqa: F401,F403
from app.models.sim_import import *  # noqa: F401,F403
from app.models.sim_tower import *  # noqa: F401,F403
from app.models.sim_unit_op import *  # noqa: F401,F403
from app.models.stream_symbol import *  # noqa: F401,F403
from app.models.system import *  # noqa: F401,F403
