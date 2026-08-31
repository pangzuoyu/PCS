# P0 骨架 + Schema 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按新模型（SUP-007 两层签署 + ADR-0019~0023）落地 P0：可运行的前后端骨架、全量 Alembic Schema、AD/Mock 认证。

**Architecture:** 单仓双包：`pcs-backend`（uv + FastAPI + SQLAlchemy 2.0 + Alembic + PG16）与 `pcs-frontend`（Vite react-ts + AntD5）。记录层公共字段（9 态门禁 + 哈希 + 变更字段组）用 SQLAlchemy Mixin 一次定义、全计算表复用；迁移手写单版本。认证 = ldap3 绑定 + Authlib JWT，Mock 通道仅 dev/test 挂载，production 启动自检。

**Tech Stack:** Python 3.12（uv）/ FastAPI / Pydantic v2 / SQLAlchemy 2.0 / Alembic / psycopg3 / authlib / ldap3 / PostgreSQL 16 / Redis 7；React 18 / TS / AntD 5 / Zustand / React Router v6 / Vite。

**Spec:** `spec/工艺专用综合计算软件——合并数据字典.md`（**PCS-DICT-ALL-003 V3.1，唯一权威，53 表，P0 严格以此为准**；V3.1 = V3.0 + ADR-0023 EquipmentTypeCode项目级覆写）、`spec/工艺专用综合计算软件需求规格说明书 Web版 P0.md`（V1.2，§3.2.1–3.2.6、§3.3、§3.4）、`spec/两层签署与变更管理增补规格说明书.md`（SUP-007）、`CONTEXT.md`（术语表）。

## Global Constraints

- Python 3.12，依赖经 uv + uv.lock 锁定；前端 React 18（不是 19）、Router v6（不是 v7）、AntD 5。
- Ruff line-length=100, target=py312，零 error；mypy 零 error；所有 Python 函数完整类型注解。
- API 路径 `/api/v1/{module}/{resource}`；除 `login` / `refresh` / `mock-login` / `health` 外全部验证 JWT。
- 统一错误 JSON：`{"code": str, "message": str, "detail": Any|None, "trace_id": str}`。
- 结构化 JSON 日志到 stdout，含 trace_id；不记录密码/令牌。
- 业务记录表**无** version/version_purpose/version_description/customer_approval_date；**不建**任何 xxx_History 表。
- 表清单与字段以 **DICT-ALL-003 V3.1 为准（53 表）**；SPEC-P0 V1.2 与之冲突处以字典为准（如 streams.stream_name、locked_by_deliverable 为 bool）。
- 主键 UUID（`<table_singular>_id`；例外：pipe_classes.class_id=string、**equipment_type_codes 复合 PK (project_id, type_code)**、project_pipe_classes 复合 PK），表名 snake_case 复数，JSONB，FK 列建索引。
- 位号终身唯一：`(project_id, tag_number)` / piping 的 `(project_id, line_no)` 唯一约束覆盖含 OBSOLETE 全记录。
- 记录层统一字段 = 字典 §1.3 模板**逐字**（无 stale_* 组、无 imported_from_workspace_id——V3.1 未定义，不自行添加）。
- ENV=production 强制禁用 Mock 认证（启动自检 + 路由不挂载）。
- 前端令牌仅内存（Zustand），不落 localStorage。
- 冲突裁决规则：**PCS-DICT-ALL-003 V3.1 > SPEC-P0 V1.2 > SUP-007 > ADR-0001~0023**（字典 V3.1 已 incorporate SUP-007 与全部 ADR，自明唯一权威；SPEC-P0 与之冲突处以字典为准）。

---

## 架构图

### 图1：P0 组件数据流

```text
┌─────────────────────────────────────────────────────────────────────┐
│                          P0 组件拓扑                                │
└─────────────────────────────────────────────────────────────────────┘

 浏览器 (localhost:5173)
   │  React18 + AntD5 + Zustand(内存令牌)
   │
   │  /api/*            /auth/mock-login(仅dev/test)
   ▼
 Vite dev proxy ────► FastAPI (localhost:8000)
                        │  create_app()/lifespan
                        │  ├─ 中间件: trace_id
                        │  ├─ 全局异常: 统一JSON错误
                        │  ├─ 路由: /health /auth/login /auth/refresh /auth/me
                        │  └─ Mock路由: 仅非production挂载
                        │
         ┌──────────────┼──────────────────┐
         │              │                  │
         ▼              ▼                  ▼
  ┌────────────┐  ┌──────────────┐  ┌──────────────┐
  │  LDAP/AD   │  │ PostgreSQL 16│  │   Redis 7    │
  │  :389      │  │  :5432       │  │   :6379      │
  │            │  │  pcs/pcs_dev │  │ (P0未使用,   │
  │ 真实域(待IT)│  │  /pcs        │  │  仅占位)     │
  │ Samba测试域 │  │  53表Schema  │  │              │
  │ (compose.ad)│  │  Alembic迁移 │  │              │
  └────────────┘  └──────────────┘  └──────────────┘

  ── 请求流 ──►   ── JWT令牌流 ──►   ── 数据流 ──►
  前端→Vite→FastAPI  登录后颁发      ORM→PG
```

### 图2：认证时序（登录 / 刷新 / 401 静默刷新）

```text
┌────────┐          ┌─────────┐          ┌──────────┐         ┌───────┐
│ 浏览器  │          │ FastAPI │          │   LDAP   │         │ 内存  │
│(前端)  │          │ (后端)  │          │  (AD)    │         │store │
└───┬────┘          └────┬────┘          └────┬─────┘         └──┬────┘
    │                    │                    │                  │
    │ ① POST /auth/login │                    │                  │
    │───────────────────►│                    │                  │
    │  {username,pass}   │ ② LDAP bind        │                  │
    │                    │───────────────────►│                  │
    │                    │ ③ 成功+groups      │                  │
    │                    │◄───────────────────│                  │
    │                    │ ④ map_groups→roles │                  │
    │                    │ ⑤ create JWT pair  │                  │
    │ ⑥ TokenPair(user)  │                    │                  │
    │◄───────────────────│                    │                  │
    │ ⑦ setTokens(pair)  │                    │                  │
    │────────────────────────────────────────────────────────────►│
    │                    │                    │                  │
    │ ⑧ GET /auth/me     │                    │                  │
    │  Authorization:    │                    │                  │
    │  Bearer <access>   │                    │                  │
    │───────────────────►│                    │                  │
    │ ⑨ 200 AuthUser     │                    │                  │
    │◄───────────────────│                    │                  │
    │                    │                    │                  │
    │ ⑩ access过期后请求  │                    │                  │
    │───────────────────►│                    │                  │
    │ ⑪ 401 AUTH_INVALID │                    │                  │
    │◄───────────────────│                    │                  │
    │ ⑫ POST /auth/refresh│                   │                  │
    │  {refresh_token}   │                    │                  │
    │───────────────────►│                    │                  │
    │ ⑬ 新TokenPair      │                    │                  │
    │◄───────────────────│                    │                  │
    │ ⑭ setTokens(new)   │                    │                  │
    │────────────────────────────────────────────────────────────►│
    │ ⑮ 原请求自动重试    │                    │                  │
    │───────────────────►│                    │                  │
    │ ⑯ 200              │                    │                  │
    │◄───────────────────│                    │                  │
    │                    │                    │                  │
    │ ⑰ refresh也401     │                    │                  │
    │◄───────────────────│                    │                  │
    │ ⑱ logout() → RequireAuth响应式跳转 /login                  │
    │────────────────────────────────────────────────────────────►│
```

关键点：
- ⑫–⑯ 是 apiFetch 的静默刷新一次重试路径（SPEC P0-FE-001）
- ⑰–⑱ 是 refresh 失败兜底：`logout()` 置空 store → RequireAuth 订阅响应式 → 自动 `<Navigate to="/login">`，无 window.location 硬跳
- Mock 路径（dev/test）：跳过①–⑥，直接 POST /auth/mock-login 按 role 签发

## 文件结构总览

```
PCS/
├── docker-compose.yml            # PG16 + Redis（开发）
├── docker-compose.ad.yml         # Samba AD 测试域（可选集成）
├── CLAUDE.md                     # 追加 P0 开发规范段
├── pcs-backend/
│   ├── pyproject.toml            # uv 项目 + ruff/mypy/pytest 配置
│   ├── .env.example
│   ├── alembic.ini
│   ├── alembic/env.py, versions/0001_p0_schema.py
│   ├── app/
│   │   ├── main.py               # 应用工厂 + 全局异常 + 路由挂载
│   │   ├── api/v1/{health,auth,mock_auth}.py + api/__init__.py(router)
│   │   ├── api/deps.py           # get_current_user
│   │   ├── core/{config,logging,errors,security,auth_ldap,auth_mock}.py
│   │   ├── db/{base,session}.py
│   │   ├── models/               # 按域分文件，__init__.py 全量导入
│   │   │   ├── enums.py, mixins.py
│   │   │   ├── project.py        # projects, workspaces, users, streams, stream_state_points (1-3,45,47)
│   │   │   ├── config_domain.py  # 配置层 11 表（含 numbering_templates/doc_no_sequences）(4-14)
│   │   │   ├── calc.py           # 计算模块 16 表 (15-30)
│   │   │   ├── equipment.py      # equipment_list/type_codes/lib + suppliers (39-42)
│   │   │   ├── deliverable.py    # 交付物 6 + 变更 2 + cost_est 无关——(31-38)
│   │   │   └── misc.py           # lineage/checklist/audit/settings/reports×2 + AI×2 + license (43-53)
│   │   └── schemas/{auth,common}.py
│   └── tests/
│       ├── conftest.py           # app/db fixture + dependency_overrides
│       ├── fakes.py              # FakeLdapConnection
│       ├── test_health.py, test_auth_ldap.py, test_auth_api.py,
│       ├── test_mock_auth.py, test_security.py, test_db_schema.py
└── pcs-frontend/
    ├── package.json, vite.config.ts, tsconfig.json, .env.development, .env.production
    └── src/{main.tsx, App.tsx, types.ts,
             pages/{LoginPage,HomePage}.tsx, components/AppLayout.tsx,
             stores/authStore.ts, services/api.ts,
             components/, hooks/, utils/}   # 空目录放 .gitkeep
```

---

### Task 0: 环境与仓库准备

**Files:**
- Create: `.gitignore`（PCS 根）
- Create: `docker-compose.yml`

**Interfaces:**
- Produces: git 仓库（后续任务 commit 用）；PG16 于 localhost:5432（pcs/pcs_dev/pcs）；Redis 于 localhost:6379。

- [ ] **Step 1: 检查工具链**

Run: `uv --version && node --version && npm --version && docker --version && docker ps`
Expected: uv ≥0.5、node 20.x、docker daemon running。任一缺失 → 停，报告用户（不要自行装）。

- [ ] **Step 2: git init + .gitignore**

```bash
cd /home/pangzy/code_project/PCS && git init -b main
```

`.gitignore`：

```gitignore
__pycache__/
*.pyc
.venv/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/
node_modules/
dist/
.env
*.local
pgdata/
```

注：`vendor/`（thermo/CoolProp/fluids 源码，~GB 级）不忽略——若 commit 过慢可改为忽略并记录。

- [ ] **Step 3: docker-compose.yml（PG16 + Redis）**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: pcs
      POSTGRES_PASSWORD: pcs_dev
      POSTGRES_DB: pcs
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pcs"]
      interval: 5s
      timeout: 3s
      retries: 10
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
volumes:
  pgdata:
```

- [ ] **Step 4: 起库并验证**

Run: `docker compose up -d postgres redis && docker compose ps`
Expected: 两容器 healthy/running。拉镜像失败（内网）→ 停，报告（fallback：本地已装 PG 或 `alembic upgrade --sql` 离线校验，见未解决问题 3）。

- [ ] **Step 5: Commit**

```bash
git add .gitignore docker-compose.yml && git commit -m "chore: P0 repo init with pg16/redis compose"
```

---

### Task 1: uv 项目 + 应用骨架 + health

**Files:**
- Create: `pcs-backend/pyproject.toml`、`pcs-backend/.env.example`
- Create: `pcs-backend/app/main.py`、`pcs-backend/app/core/config.py`、`pcs-backend/app/core/logging.py`、`pcs-backend/app/core/errors.py`
- Create: `pcs-backend/app/api/__init__.py`、`pcs-backend/app/api/v1/health.py`
- Test: `pcs-backend/tests/test_health.py`、`pcs-backend/tests/__init__.py`

**Interfaces:**
- Produces: `create_app() -> FastAPI`（app/main.py）；`get_settings() -> Settings`（lru_cache，字段见下）；错误格式 `{"code","message","detail","trace_id"}`；`GET /api/v1/health`。
- 后续任务依赖：`app.core.config.get_settings`、`app.db.session.get_engine`（Task 2）。

- [ ] **Step 1: pyproject.toml**

```toml
[project]
name = "pcs-backend"
version = "0.1.0"
description = "PCS 工艺专用综合计算软件 后端"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy>=2.0.30",
    "alembic>=1.13",
    "psycopg[binary]>=3.1",
    "pydantic>=2.7",
    "pydantic-settings>=2.2",
    "authlib>=1.3",
    "ldap3>=2.9",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "httpx>=0.27",
    "ruff>=0.4",
    "mypy>=1.10",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.12"
ignore_missing_imports = true
check_untyped_defs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: .env.example**

```bash
# 复制为 .env 使用
ENV=development
SECRET_KEY=change-me-32-bytes-minimum-secret!!
DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
LDAP_URL=ldap://localhost:389
LDAP_BASE_DN=DC=test,DC=local
LDAP_USER_DN_TEMPLATE=cn={username},CN=Users,DC=test,DC=local
LDAP_GROUP_ROLE_MAP=DESIGNER_GROUP:DESIGNER,CHECKER_GROUP:CHECKER,REVIEWER_GROUP:REVIEWER,APPROVER_GROUP:APPROVER,ADMIN_GROUP:SYSADMIN
```

- [ ] **Step 3: app/core/config.py**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"  # development | test | production
    secret_key: str = "dev-secret-key-not-for-production--"
    database_url: str = "postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    ldap_url: str = "ldap://localhost:389"
    ldap_base_dn: str = "DC=test,DC=local"
    ldap_user_dn_template: str = "cn={username},CN=Users,DC=test,DC=local"
    ldap_group_role_map: str = (
        "DESIGNER_GROUP:DESIGNER,CHECKER_GROUP:CHECKER,REVIEWER_GROUP:REVIEWER,"
        "APPROVER_GROUP:APPROVER,ADMIN_GROUP:SYSADMIN"
    )

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    def group_role_map(self) -> dict[str, str]:
        return dict(
            pair.split(":", 1) for pair in self.ldap_group_role_map.split(",") if pair
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: app/core/logging.py（JSON 结构化）**

```python
import json
import logging
import sys
import uuid


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "trace_id": getattr(record, "trace_id", None),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def new_trace_id() -> str:
    return uuid.uuid4().hex
```

- [ ] **Step 5: app/core/errors.py + app/main.py + health 路由**

`app/core/errors.py`：

```python
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class PcsError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, detail: Any = None):
        self.code, self.message, self.status, self.detail = code, message, status, detail


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PcsError)
    async def _(request: Request, exc: PcsError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content=ErrorResponse(
                code=exc.code, message=exc.message, detail=exc.detail,
                trace_id=getattr(request.state, "trace_id", ""),
            ).model_dump(),
        )

    @app.exception_handler(StarletteHTTPException)  # eng-review Issue 4：404 等统一信封
    async def _(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                code=f"HTTP_{exc.status_code}", message=str(exc.detail), detail=None,
                trace_id=getattr(request.state, "trace_id", ""),
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)  # 422 统一信封
    async def _(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                code="VALIDATION_ERROR", message="request validation failed",
                detail=jsonable_encoder(exc.errors()),
                trace_id=getattr(request.state, "trace_id", ""),
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def _(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                code="INTERNAL_ERROR", message="internal server error", detail=None,
                trace_id=getattr(request.state, "trace_id", ""),
            ).model_dump(),
        )


class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: Any = None
    trace_id: str
```

`app/api/v1/health.py`：

```python
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    database: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    # Task 2 接入 check_database() 后升级为真实探测（见 Task 2 Step 3）
    return HealthResponse(status="ok", database="unknown")
```

`app/main.py`：

```python
import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request

from app.api import api_router
from app.core.config import get_settings
from app.core.errors import install_exception_handlers
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Task 10 在此注入：from app.core.auth_mock import assert_mock_not_enabled; assert_mock_not_enabled(app)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()
    app = FastAPI(title="PCS Backend", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def add_trace_id(request: Request, call_next):
        request.state.trace_id = uuid.uuid4().hex
        return await call_next(request)

    install_exception_handlers(app)
    app.include_router(api_router)
    if not settings.is_production:
        from app.api.v1.mock_auth import router as mock_router

        app.include_router(mock_router)  # production 不挂载（P0-AUTH-002）
    return app


app = create_app()
```

`app/api/__init__.py`：

```python
from fastapi import APIRouter

from app.api.v1 import auth, health

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)  # Task 9 提供；先建空文件占位 import 会被 lint 拒
```

注：Task 1 阶段先不含 `auth` 行，Task 9 加回。空包 `app/api/v1/auth.py` 先不建。

- [ ] **Step 6: 写失败测试 tests/test_health.py + tests/test_errors.py**

```python
# tests/test_health.py
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert body["database"] in ("up", "down")
```

```python
# tests/test_errors.py —— eng-review Issue 4：全错误路径统一信封
from fastapi.testclient import TestClient

from app.main import create_app


def test_404_uses_envelope() -> None:
    resp = TestClient(create_app()).get("/api/v1/nope")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "HTTP_404" and body["trace_id"]


def test_405_uses_envelope() -> None:
    # Task 1 阶段无业务 POST 端点，用 health 打 POST 触发 HTTPException(405)
    resp = TestClient(create_app()).post("/api/v1/health")
    assert resp.status_code == 405
    assert resp.json()["code"] == "HTTP_405"
```

422 信封测试放 Task 9（login 路由就绪后，tests/test_auth_api.py 追加）：

```python
def test_422_uses_envelope(client):  # eng-review Issue 4
    resp = client.post("/api/v1/auth/login", json={"username": "x"})  # 缺 password
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "VALIDATION_ERROR" and body["trace_id"]
```

（无 DB 时 database=down、status=degraded 也算 200——SPEC 只要求返回状态。）

- [ ] **Step 7: 安装依赖并跑测试**

```bash
cd pcs-backend && uv sync
uv run pytest tests/test_health.py -v
```
Expected: PASS（`uv sync` 网络失败 → 停，报告）。

- [ ] **Step 8: 验证验收标准**

```bash
uv run uvicorn app.main:app --reload &   # 起后 curl
curl -s localhost:8000/api/v1/health ; curl -s -o /dev/null -w "%{http_code}" localhost:8000/docs
kill %1
```
Expected: health JSON；/docs 返回 200。

- [ ] **Step 9: Commit**

```bash
git add pcs-backend && git commit -m "feat(backend): uv project skeleton, health endpoint, json logging, unified errors"
```

---

### Task 2: DB 会话层

**Files:**
- Create: `pcs-backend/app/db/base.py`、`pcs-backend/app/db/session.py`、`pcs-backend/app/models/__init__.py`

**Interfaces:**
- Produces: `Base`（DeclarativeBase，命名约定 metadata——迁移约束名稳定）；`get_engine() -> Engine`；`check_database() -> bool`。不提供 get_db 依赖（P0 无 DB 端点，P1 加）。

- [ ] **Step 1: app/db/base.py**

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

- [ ] **Step 2: app/db/session.py**

```python
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_settings().database_url,
            pool_size=5,
            max_overflow=45,
            pool_pre_ping=True,
        )
    return _engine


def check_database() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
```

注：不提供 `get_db` 依赖——P0 无业务端点用 DB（YAGNI），P1 加。

- [ ] **Step 3: 升级 health 为真实探测**

`app/api/v1/health.py` 顶部 `from app.db.session import check_database`，端点体改为：

```python
    db_ok = check_database()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database="up" if db_ok else "down",
    )
```

重跑 `uv run pytest tests/test_health.py -v` → PASS（无库时 degraded/down 也 200）。

`tests/test_health.py` 追加两条分支测试（eng-review T-b/T-c）：

```python
def test_health_db_down(monkeypatch):  # T-c：down 分支
    import app.api.v1.health as health_mod

    monkeypatch.setattr(health_mod, "check_database", lambda: False)
    resp = TestClient(create_app()).get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded" and body["database"] == "down"


def test_unhandled_exception_500_envelope(monkeypatch):  # T-b：兜底 500 信封
    import app.api.v1.health as health_mod

    def _boom() -> bool:
        raise RuntimeError("boom")

    monkeypatch.setattr(health_mod, "check_database", _boom)
    resp = TestClient(create_app(), raise_server_exceptions=False).get(
        "/api/v1/health"
    )
    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == "INTERNAL_ERROR" and body["trace_id"]
```

- [ ] **Step 4: models 包占位**

`app/models/__init__.py` 暂空（带 docstring），Task 3–7 逐步填充最终为：

```python
"""全部 ORM 模型。alembic/env.py 依赖本包导入即注册全部表。"""
from app.models.config_domain import *  # noqa: F401,F403
from app.models.deliverable import *  # noqa: F401,F403
from app.models.equipment import *  # noqa: F401,F403
from app.models.misc import *  # noqa: F401,F403
from app.models.project import *  # noqa: F401,F403
from app.models.calc import *  # noqa: F401,F403
```

- [ ] **Step 5: 测试**

```bash
uv run pytest tests/ -v && uv run ruff check . && uv run mypy app/
```
Expected: 全 PASS、零 error。

- [ ] **Step 6: Commit**

```bash
git add pcs-backend && git commit -m "feat(backend): db base with naming convention, engine/session"
```

---

### Task 3: 枚举 + Mixin + 项目物流域模型

**Files:**
- Create: `pcs-backend/app/models/enums.py`、`pcs-backend/app/models/mixins.py`、`pcs-backend/app/models/project.py`

**Interfaces:**
- Produces（后续域模型复用）：
  - `RecordSignStatus9`（PG ENUM `recordsignstatus`：DRAFT/IN_APPROVAL/CHECKED/CHECK_REJECTED/STALE/CHANGE_PENDING/CHANGED/REVERSAL_PENDING/OBSOLETE）
  - `StreamSignStatus`（PG ENUM `streamsignstatus`：DRAFT/IN_APPROVAL/CHECKED/OBSOLETE）
  - `TimestampMixin`（created_by/created_at/updated_at）
  - `RecordMixin`（DICT-ALL-003 V3.1 §1.3 模板**逐字**：9 态 + record_hash + approval_* + locked_by_deliverable(bool) + change_/reversal_/obsoleted_ 精确字段组；**无 stale_* 组、无 imported_from_workspace_id**）
  - 模型类：`Project`、`Workspace`、`User`、`Stream`、`StreamStatePoint`

- [ ] **Step 1: enums.py**

```python
import enum


class RecordSignStatus9(str, enum.Enum):
    DRAFT = "DRAFT"
    IN_APPROVAL = "IN_APPROVAL"
    CHECKED = "CHECKED"
    CHECK_REJECTED = "CHECK_REJECTED"
    STALE = "STALE"
    CHANGE_PENDING = "CHANGE_PENDING"
    CHANGED = "CHANGED"
    REVERSAL_PENDING = "REVERSAL_PENDING"
    OBSOLETE = "OBSOLETE"


class StreamSignStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    IN_APPROVAL = "IN_APPROVAL"
    CHECKED = "CHECKED"
    OBSOLETE = "OBSOLETE"


class WorkspaceType(str, enum.Enum):
    FORMAL = "FORMAL"
    PERSONAL = "PERSONAL"
    TEMPORARY = "TEMPORARY"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
```

（其余领域枚举 FluidCategory/ToxicClass/… P0 阶段一律 `String(30~50)` + comment，不建 PG ENUM——减少迁移漂移；核心三态机 RecordSignStatus/StreamSignStatus/DeliverableSignStatus 除外。DeliverableSignStatus 枚举类一并加入 enums.py：DRAFT/PENDING/APPROVED/OBSOLETE，native enum 名 `deliverablesignstatus`，Task 6 用。）

- [ ] **Step 2: mixins.py（严格按 DICT-ALL-003 §1.3）**

```python
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.models.enums import RecordSignStatus9


class TimestampMixin:
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )


class RecordMixin(TimestampMixin):
    """业务记录统一字段（DICT-ALL-003 V3.1 §1.3，逐字对齐）。

    tag_number 可空入 mixin（§1.3 模板适用于全部 16 计算表 + equipment_list）；
    需要位号的表在类体重声明 NOT NULL 覆盖；piping_results 用 line_no，tag_number 留空。
    """

    tag_number: Mapped[str | None] = mapped_column(
        String(50), comment="位号/管道号，终身唯一；piping_results 用 line_no 此处留空"
    )
    sign_status: Mapped[RecordSignStatus9] = mapped_column(
        Enum(RecordSignStatus9, name="recordsignstatus", native_enum=True),
        nullable=False, default=RecordSignStatus9.DRAFT, index=True,
        comment="记录门禁 9 态（SUP-007 §3.1）",
    )
    record_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, default="",
        comment="SHA-256，数值规范化舍入 6 位有效数字，仅设计参数参与；未计算时空串",
    )
    approval_step: Mapped[int | None] = mapped_column(comment="IN_APPROVAL 当前步骤(1-based)")
    approval_depth: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="该记录类型批准深度快照(1-4)，默认最低 1"
    )
    approval_role: Mapped[str | None] = mapped_column(
        String(30), comment="当前待批角色 ApprovalRole"
    )
    locked_by_deliverable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="被交付物快照绑定即锁定"
    )

    # change_* 组（ADR-0002，字典 §1.3 逐字）
    change_pending_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_resolved_by: Mapped[str | None] = mapped_column(String(64))
    change_resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_abandoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_abandoned_reason: Mapped[str | None] = mapped_column(String(500))

    # obsoleted_* 组（ADR-0009，字典 §1.3 逐字）
    obsoleted_reason: Mapped[str | None] = mapped_column(String(200))
    obsoleted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    obsoleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    obsoleted_via_deliverable_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, comment="已绑定记录经 RECORD_CANCELLATION 变更单弃用"
    )

    # reversal_* 组（ADR-0010，字典 §1.3 逐字）
    reversal_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversal_requested_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    reversal_reason: Mapped[str | None] = mapped_column(String(500))
    reversal_approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    reversal_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @declared_attr
    def project_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(ForeignKey("projects.project_id"), index=True)

    @declared_attr
    def workspace_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(ForeignKey("workspaces.workspace_id"), index=True)


class TaggedRecordMixin(RecordMixin):
    """需要位号的记录表（eng-review Issue 5）：tag_number NOT NULL + 项目内终身唯一。

    15 张计算表 + equipment_list 用；piping_results 直接用 RecordMixin（line_no）。
    约束名由 naming convention 生成（uq_<table>_project_id），每表独立。
    """

    tag_number: Mapped[str] = mapped_column(String(50))

    __table_args__ = (UniqueConstraint("project_id", "tag_number"),)
```

- [ ] **Step 3: project.py（5 表：projects / workspaces / users / streams / stream_state_points，字典表1/2/3/45/47 逐字）**

```python
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import StreamSignStatus, UserStatus, WorkspaceType
from app.models.mixins import RecordMixin, TimestampMixin


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_no: Mapped[str] = mapped_column(String(50), unique=True)
    project_name: Mapped[str] = mapped_column(String(200))
    project_name_cn: Mapped[str | None] = mapped_column(String(200))
    owner_company: Mapped[str] = mapped_column(String(200))
    contractor_company: Mapped[str | None] = mapped_column(String(200))
    engineer_name: Mapped[str | None] = mapped_column(String(200))
    dd_contractor_name: Mapped[str | None] = mapped_column(String(200))
    feed_contractor_name: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str] = mapped_column(String(500))
    site_address: Mapped[str | None] = mapped_column(String(500))
    project_type: Mapped[str] = mapped_column(String(30))
    design_phase: Mapped[str] = mapped_column(String(30))
    total_capacity: Mapped[float | None] = mapped_column(Float)
    total_capacity_unit: Mapped[str | None] = mapped_column(String(20))
    plant_count: Mapped[int | None] = mapped_column(Integer)
    single_plant_capacity: Mapped[float | None] = mapped_column(Float)
    single_plant_capacity_unit: Mapped[str | None] = mapped_column(String(20))
    reference_plant: Mapped[str | None] = mapped_column(String(200))
    unit_system: Mapped[str] = mapped_column(String(20))
    bedd_json: Mapped[dict | None] = mapped_column(JSONB)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.workspace_id", use_alter=True, name="fk_projects_workspace_id"),
        comment="项目所属 FORMAL 工作区；use_alter 破解 projects↔workspaces 循环",
    )
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class Workspace(Base):
    __tablename__ = "workspaces"
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_type: Mapped[str] = mapped_column(String(20))  # WorkspaceType
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.project_id"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_days: Mapped[int | None] = mapped_column(
        Integer, comment="个人 90 / 临时 7"
    )


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(200))
    roles: Mapped[list[str]] = mapped_column(
        JSONB, default=list,
        comment="ApprovalRole 7 值：DESIGNER/CHECKER/REVIEWER/APPROVER/SYSADMIN/PROCESS_CONTROLLER/DATA_ADMIN",
    )
    ad_groups: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default=UserStatus.ACTIVE.value)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Stream(TimestampMixin, Base):
    """物流=管段（ADR-0019）。4 态简化门禁（ADR-0014）。字典表2 逐字。"""
    __tablename__ = "streams"
    __table_args__ = (
        UniqueConstraint("project_id", "stream_name", name="uq_streams_project_stream_name"),
    )
    stream_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.project_id"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.workspace_id"), index=True
    )
    stream_name: Mapped[str] = mapped_column(String(100), comment="管段物流号，如 S-101")
    description: Mapped[str | None] = mapped_column(String(500))
    phase: Mapped[str | None] = mapped_column(String(20), comment="StreamPhase")
    temp: Mapped[float | None] = mapped_column(Float, comment="基准工况 °C")
    press: Mapped[float | None] = mapped_column(Float)
    mass_flow: Mapped[float | None] = mapped_column(Float, comment="kg/h")
    molar_flow: Mapped[float | None] = mapped_column(Float, comment="kmol/h")
    volumetric_flow: Mapped[float | None] = mapped_column(Float, comment="m³/h")
    std_gas_flow: Mapped[float | None] = mapped_column(Float, comment="Nm³/h")
    composition_json: Mapped[dict | None] = mapped_column(JSONB)
    vapor_composition_json: Mapped[dict | None] = mapped_column(JSONB, comment="两相流必填")
    liquid_composition_json: Mapped[dict | None] = mapped_column(JSONB, comment="两相流必填")
    density: Mapped[float | None] = mapped_column(Float)
    viscosity_dynamic: Mapped[float | None] = mapped_column(Float)
    viscosity_kinematic: Mapped[float | None] = mapped_column(Float)
    thermal_conductivity: Mapped[float | None] = mapped_column(Float)
    specific_heat: Mapped[float | None] = mapped_column(Float)
    molecular_weight: Mapped[float | None] = mapped_column(Float)
    compressibility_factor: Mapped[float | None] = mapped_column(Float)
    vapor_fraction: Mapped[float | None] = mapped_column(Float)
    enthalpy: Mapped[float | None] = mapped_column(Float)
    entropy: Mapped[float | None] = mapped_column(Float)
    bulk_density_min: Mapped[float | None] = mapped_column(Float)
    bulk_density_max: Mapped[float | None] = mapped_column(Float)
    true_density: Mapped[float | None] = mapped_column(Float)
    particle_size_avg: Mapped[float | None] = mapped_column(Float)
    particle_size_range: Mapped[str | None] = mapped_column(String(100))
    particle_shape: Mapped[str | None] = mapped_column(String(100))
    repose_angle: Mapped[float | None] = mapped_column(Float)
    vessel_cone_angle: Mapped[float | None] = mapped_column(Float)
    distillation_json: Mapped[dict | None] = mapped_column(JSONB, comment="馏程 IBP→FBP")
    sara_json: Mapped[dict | None] = mapped_column(JSONB)
    elemental_json: Mapped[dict | None] = mapped_column(JSONB)
    metals_json: Mapped[dict | None] = mapped_column(JSONB)
    feedstock_specs_json: Mapped[dict | None] = mapped_column(JSONB)
    product_specs_json: Mapped[dict | None] = mapped_column(JSONB)
    data_mode: Mapped[str] = mapped_column(
        String(20), comment="StreamDataMode：CHEMICAL/PETROLEUM/SOLID"
    )
    property_estimation_json: Mapped[dict | None] = mapped_column(JSONB)
    pseudo_components_json: Mapped[list | None] = mapped_column(JSONB)
    lab_report_ref: Mapped[str | None] = mapped_column(String(200))
    upstream_stream_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("streams.stream_id")
    )
    upstream_equipment_type: Mapped[str | None] = mapped_column(
        String(30), comment="PUMP/CV/PIPE/HEAT/RESTRICTION/FLASH"
    )
    upstream_equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, comment="设备记录 ID（多态，不强 FK）"
    )
    change_type: Mapped[str | None] = mapped_column(
        String(30),
        comment="StreamChangeType：ISOENTHALPIC/FRICTION_PRESSURE_DROP/HEAT_EXCHANGE/PUMP_WORK",
    )
    source_type: Mapped[str] = mapped_column(
        String(30),
        comment="SIM_IMPORT/MANUAL_ENTRY/LAB_REPORT/FLASH_CALCULATED/DEVICE_CALCULATED",
    )
    source_file: Mapped[str | None] = mapped_column(String(200))
    sign_status: Mapped[StreamSignStatus] = mapped_column(
        Enum(StreamSignStatus, name="streamsignstatus", native_enum=True),
        nullable=False, default=StreamSignStatus.DRAFT, index=True,
    )
    approval_step: Mapped[int | None] = mapped_column(comment="当前校对步骤")
    approval_depth: Mapped[int] = mapped_column(Integer, nullable=False, comment="校对深度 1~2")
    checked_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    last_change_reason: Mapped[str | None] = mapped_column(
        String(30),
        comment="StreamChangeReason：SIM_REIMPORT/CLIENT_DATA_UPDATE/DESIGN_CONFIRMATION/IMPORT_ERROR_FIX/OTHER",
    )
    last_change_note: Mapped[str | None] = mapped_column(String(500))
    last_changed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    last_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StreamStatePoint(Base):
    """工况状态点（ADR-0020）。无 sign_status（跟随所属物流）。字典表3 逐字。"""
    __tablename__ = "stream_state_points"
    state_point_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    stream_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("streams.stream_id"), index=True
    )
    state_label: Mapped[str] = mapped_column(String(50))
    case_type: Mapped[str] = mapped_column(String(20), comment="NORMAL/MIN/MAX/ALTERNATE")
    temp: Mapped[float] = mapped_column(Float)
    press: Mapped[float] = mapped_column(Float)
    phase: Mapped[str] = mapped_column(String(20))
    vapor_fraction: Mapped[float | None] = mapped_column(Float)
    mass_flow: Mapped[float] = mapped_column(Float)
    composition_json: Mapped[dict] = mapped_column(JSONB)
    vapor_composition_json: Mapped[dict | None] = mapped_column(JSONB)
    liquid_composition_json: Mapped[dict | None] = mapped_column(JSONB)
    density: Mapped[float | None] = mapped_column(Float)
    viscosity_dynamic: Mapped[float | None] = mapped_column(Float)
    enthalpy: Mapped[float | None] = mapped_column(Float)
    entropy: Mapped[float | None] = mapped_column(Float)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    estimated_flags_json: Mapped[dict | None] = mapped_column(JSONB)
    profile_json: Mapped[dict | None] = mapped_column(
        JSONB, comment="沿程剖面 distance/pressures/temperatures"
    )
    source_type: Mapped[str] = mapped_column(
        String(30),
        comment="SIM_IMPORT/MANUAL_ENTRY/FLASH_CALCULATED/DEVICE_CALCULATED（无 LAB_REPORT）",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 4: lint/type/test**

```bash
uv run ruff check . && uv run mypy app/ && uv run pytest -q
```
Expected: 零 error（此时无新测试，原测试仍绿）。

- [ ] **Step 5: Commit**

```bash
git add pcs-backend && git commit -m "feat(db): enums, record mixin, project/workspace/user/stream/state-point models"
```

---

### Task 4: 配置域 11 表模型（字典表4–14）

**Files:**
- Create: `pcs-backend/app/models/config_domain.py`

**Interfaces:**
- Produces: `ConfigAsset`、`ConfigVersion`、`ConfigApproval`、`FormulaDefinition`、`CoefficientTable`、`TemplateFile`、`ProjectTemplate`、`PipeClass`、`ProjectPipeClass`、`NumberingTemplate`、`DocNoSequence`（numbering 两表归配置层——字典 V3.0 域划分）。
- 消费：`Base`、`TimestampMixin`；`DocNoSequence.template_id` FK→numbering_templates（本文件内）。

- [ ] **Step 1: 建模规则（本任务与 Task 5/6/7 通用映射）**

对照字典 V3.1 对应表逐字段翻译：
- `string(N)` → `String(N)`；`string` 无长度 → `String(200)`；`text` → `Text`
- `float` → `Float`；`int` → `Integer`；`bool` → `Boolean`；`date` → `Date`；`decimal` → `Numeric`
- `JSON`/`JSON[]` → `JSONB`（`Mapped[dict | None]` 或 `Mapped[list | None]`）
- 枚举 → `String(30)` + `comment=枚举值列表`（三态机除外）；`enum[]` → JSONB
- PK：UUID default uuid4；例外：`pipe_classes.class_id` String(20) PK、`project_pipe_classes` 复合 PK (project_id, class_id)
- ✅ 必填 → `nullable=False`；❌ → nullable。FK 列 `index=True`

- [ ] **Step 2: 写模型（示例两表，其余按规则机械翻译，字段=字典表4–14 逐字）**

```python
class ConfigAsset(TimestampMixin, Base):
    __tablename__ = "config_assets"
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(30), comment="CATEGORY_1~6")
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(500))
    current_version: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", comment="ConfigStatus")
    content_json: Mapped[dict | None] = mapped_column(JSONB)


class PipeClass(TimestampMixin, Base):
    """管道等级。class_id=等级代码（string PK，字典表11）。"""
    __tablename__ = "pipe_classes"
    class_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    class_name: Mapped[str] = mapped_column(String(200))
    material_standard: Mapped[str] = mapped_column(String(100))
    corrosion_allowance: Mapped[float] = mapped_column(Float, comment="mm")
    design_pressure: Mapped[float] = mapped_column(Float, comment="MPaG")
    design_temperature: Mapped[float] = mapped_column(Float, comment="°C")
    fluid_service: Mapped[str | None] = mapped_column(String(100))
    allowable_stress_json: Mapped[dict] = mapped_column(JSONB, comment="引用 COMMON 可覆写")
    dn_series_json: Mapped[dict] = mapped_column(JSONB, comment="{min,max}")
    sch_series_json: Mapped[list] = mapped_column(JSONB)
    flange_class: Mapped[str] = mapped_column(String(20))
    fitting_type: Mapped[str | None] = mapped_column(String(50), comment="FittingType")
    branch_table_json: Mapped[dict | None] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(20), comment="COMPANY_STD/PROJECT")
    version: Mapped[str] = mapped_column(String(50), comment="配置版本（非记录层 Rev）")
    status: Mapped[str] = mapped_column(String(20), comment="DRAFT/ACTIVE/OBSOLETE")
```

其余 9 表要点：`config_versions.version_code` String(50) ✅；`config_approvals`（version_id FK、approver_role String(30)、decision String(20)、timestamp）；`formula_definitions.expression` Text ✅、`unit_tests_json` JSONB ✅；`coefficient_tables.data_json` ✅；`template_files.file_type` String(10)、`placeholders_json` ✅；`project_templates.default_config_json` ✅（comment 注明含 record_approval_config/stream_approval_config/signature_matrices/numbering_config/customer_approval_config/doc_no_config/**equipment_type_codes_config**）；`project_pipe_classes` 复合 PK；`numbering_templates`（segments_json ✅、separator ✅、revision_separate Boolean ✅、deliverable_mappings_json ✅、status）；`doc_no_sequences`（scope_key ✅ 如 "PE-LST"、current_value ✅ int）。

- [ ] **Step 3: 校验 + Commit**

```bash
uv run ruff check . && uv run mypy app/
git add pcs-backend && git commit -m "feat(db): config domain 11 tables (incl. numbering)"
```

---

### Task 5: 计算域 16 表 + 集成层 4 表模型（字典表15–30、39–42）

**Files:**
- Create: `pcs-backend/app/models/calc.py`、`pcs-backend/app/models/equipment.py`

**Interfaces:**
- Produces: 16 个计算结果表类 + `EquipmentList`、`EquipmentTypeCode`、`EquipmentLib`、`Supplier`。
- 位号约定（eng-review 定案）：piping 外的记录表一律继承 **`TaggedRecordMixin`**（零样板获得 tag_number NOT NULL + (project_id, tag_number) 唯一约束）；**piping_results 直接继承 RecordMixin**，仅用 line_no，唯一约束 `(project_id, line_no)` 含 OBSOLETE（字典表16 注）。
- `CostEstResult.equipment_id` FK→equipment_list（字典表30）。

- [ ] **Step 1: calc.py——PipingResult 完整示例（字典表16 特有字段逐字）**

```python
import uuid

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import RecordMixin


class PipingResult(RecordMixin, Base):
    """管道记录（字典表16）。line_no 位号唯一含 OBSOLETE。"""
    __tablename__ = "piping_results"
    __table_args__ = (
        UniqueConstraint("project_id", "line_no", name="uq_piping_results_project_line_no"),
    )
    pipe_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    seq_no: Mapped[int] = mapped_column(comment="一览表序号")
    line_no: Mapped[str] = mapped_column(String(50))
    line_size: Mapped[str] = mapped_column(String(20))
    material_class: Mapped[str] = mapped_column(
        String(20), ForeignKey("pipe_classes.class_id"), comment="材料等级"
    )
    fluid_code: Mapped[str] = mapped_column(String(10))
    fluid_name: Mapped[str] = mapped_column(String(100))
    fluid_phase: Mapped[str] = mapped_column(String(20))
    fluid_category: Mapped[str] = mapped_column(String(10), comment="D/M/NORMAL")
    toxic_class: Mapped[str | None] = mapped_column(String(30))
    pipe_grade: Mapped[str | None] = mapped_column(String(30))
    insulation_code: Mapped[str | None] = mapped_column(String(20))
    insulation_thickness: Mapped[float | None] = mapped_column(Float, comment="mm")
    paint_code: Mapped[str | None] = mapped_column(String(20))
    tracing_type: Mapped[str | None] = mapped_column(String(10), comment="J/T/TE/NONE")
    holding_temp: Mapped[float | None] = mapped_column(Float, comment="°C")
    source_pid: Mapped[str] = mapped_column(String(50), comment="P&ID 引用")
    line_from: Mapped[str] = mapped_column(String(100))
    line_to: Mapped[str] = mapped_column(String(100))
    norm_oper_press: Mapped[float] = mapped_column(Float, comment="MPaG")
    max_oper_press: Mapped[float] = mapped_column(Float)
    norm_oper_temp: Mapped[float] = mapped_column(Float, comment="°C")
    max_oper_temp: Mapped[float] = mapped_column(Float)
    alt_norm_oper_press: Mapped[float | None] = mapped_column(Float)
    alt_max_oper_press: Mapped[float | None] = mapped_column(Float)
    alt_norm_oper_temp: Mapped[float | None] = mapped_column(Float)
    alt_max_oper_temp: Mapped[float | None] = mapped_column(Float)
    design_press: Mapped[float] = mapped_column(Float, comment="MPaG")
    design_vacuum: Mapped[float | None] = mapped_column(Float)
    design_temp: Mapped[float] = mapped_column(Float)
    design_min_temp: Mapped[float | None] = mapped_column(Float)
    piping_category: Mapped[str] = mapped_column(String(10), comment="GC1/GC2/GC3")
    pressure_test_medium: Mapped[str] = mapped_column(String(10), comment="WATER/AIR")
    pressure_test_press: Mapped[float] = mapped_column(Float)
    ndt_method: Mapped[str | None] = mapped_column(String(10), comment="RT/UT/MT/PT/NONE")
    ndt_ratio: Mapped[float | None] = mapped_column(Float, comment="%")
    ndt_tech_level: Mapped[str | None] = mapped_column(String(10))
    leak_test_medium: Mapped[str | None] = mapped_column(String(10), comment="AIR/WATER")
    leak_test_press: Mapped[float | None] = mapped_column(Float)
    check_class: Mapped[str] = mapped_column(String(5), comment="I~V")
    cleaning_method: Mapped[list | None] = mapped_column(JSONB, comment="PI/PA/DG/SO 多选")
    stress_analysis_level: Mapped[str | None] = mapped_column(String(10))
    remark: Mapped[str | None] = mapped_column(String(500))
```

- [ ] **Step 2: 其余 15 表（特有字段=字典表15、17–30 逐字 + RecordMixin）**

- `FlashResult`（表15）：flash_id PK、stream_id FK→streams ✅、calc_type String(30) ✅、method String(20) ✅、input_json/output_json JSONB ✅。
- `PumpResult(TaggedRecordMixin, Base)`（表18）：pump_id PK；basic_info_json/fluid_properties_json/flow_rates_json/suction_calculation_json/discharge_calculation_json/differential_pressure_json/design_pressure_json/power_consumption_json/control_valve_json/equivalent_length_json/pressure_drop_details_json/line_references_json 全 JSONB ✅；actual_head/actual_efficiency/actual_motor_power/actual_npshr Float ❌；vendor_model String；actual_data_confirmed Boolean ❌。
- `PsvResult`（表19）：psv_id PK、set_pressure/relief_capacity/orifice_area/blowdown Float ✅、orifice_designation/inlet_size/outlet_size String ✅、relief_scenario JSONB ✅（enum[] 多选）。
- `FlareSystemResult`（表20）、`PipeNetworkResult`（表17）、`VesselResult`（表21）、`SepEquipResult`（表22）、`HeatResult`（表23，exchanger_category ✅ + air_side_json/design_conditions_json/enthalpy_table_json 空冷器列）、`CvResult`（表24，cv_value/flow_rate/pressure_drop ✅、choked_flow Boolean ✅）、`RestrictionResult`（表25，restriction_type ✅）、`CoolingTowerResult`（表26）、`PsychroResult`（表27，calc_type/input_json/output_json）、`OpenChannelResult`（表28，channel_type/cross_section_json/flow_rate/depth/velocity/slope）、`FiltrationResult`（表29，filter_type/area/cycle_time/pressure_drop）——同 PumpResult 一律继承 `TaggedRecordMixin`（字典 §1.3 模板 tag_number ✅；piping 除外）。
- `CostEstResult`（表30）：cost_est_id PK、equipment_id FK→equipment_list ✅、estimated_cost Numeric ✅、currency String(10) ✅、cost_index_year Integer ✅。

- [ ] **Step 3: equipment.py（字典表39–42 逐字）**

`EquipmentList(TaggedRecordMixin, Base)`：equipment_id PK + 字典表39 全部字段组逐字翻译（标识/类型/来源/状态/设计参数/采购/图纸/交付/安装/重量/涂装/工程/实际数据）；**`type_code` + `project_id` 复合 FK→equipment_type_codes(project_id, type_code) ✅（V3.1 ADR-0023；项目级覆写优先于公司级）**；`source_record_id` Uuid ❌（多态）；`record_hash` 来自 Mixin，类 docstring 注明哈希范围=tag_number+type_code+design_parameters_json+source_module+source_record_id（商务/采购字段不参与）。
`EquipmentTypeCode`（表40，V3.1 ADR-0023）：**复合 PK (project_id, type_code)**；`project_id` Uuid FK→projects NULL（null=公司级默认）；`type_code` String(5)；equipment_description ✅、description_cn、category ✅（STATIC/ROTATING/PACKAGE/ELECTRICAL/INSTRUMENT/OTHER）、is_process_equipment/is_pressure_vessel Boolean ✅、source、status ✅；**`__table_args__ = UniqueConstraint("project_id", "type_code", name="uq_equipment_type_codes_project_type")`**（P0 仅预置约 80 种公司级默认 `project_id IS NULL`；项目级覆写 P2+ 模板导入后启用）。
`EquipmentLib`（表41）：equip_id UUID PK、type_code String(5)、size/weight/material/standard_drawing_no/process_description（AI 预留语义描述）、cost Numeric、cost_currency、cost_year Integer、status ✅、created_by/at、updated_at。
`Supplier`（表42）：supplier_id UUID PK、supplier_name ✅、supplier_type ✅（MANUFACTURER/AGENT/TRADER）、contact_json、qualification_json（JSON[]）、rating（A/B/C/UNRATED）、approved_by、approved_date Date。

- [ ] **Step 4: 校验 + Commit**

```bash
uv run ruff check . && uv run mypy app/
git add pcs-backend && git commit -m "feat(db): 16 calc result tables + equipment/supplier integration tables"
```

---

### Task 6: 交付物域 9 表模型（字典表31–38，SUP-007 核心）

**Files:**
- Create: `pcs-backend/app/models/deliverable.py`

**Interfaces:**
- Produces: `Deliverable`、`DeliverableVersion`、`DeliverableRecordBinding`、`SignatureMatrix`、`ProjectSignatureMatrixBinding`、`CustomerApprovalAttachment`、`ChangeNoticeDetail`、`RecordChangeSnapshot`。
- `Deliverable.matrix_id` FK→signature_matrices ✅（字典表31）；`numbering_template_id` FK→numbering_templates（Task 4 已建）。

- [ ] **Step 1: 核心三表 + 签署矩阵两表完整代码**

```python
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import DeliverableSignStatus
from app.models.mixins import TimestampMixin


class Deliverable(TimestampMixin, Base):
    """交付物（含变更单，ADR-0008）。字典表31 逐字。"""
    __tablename__ = "deliverables"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "deliverable_type", "scope_type", "scope_value",
            name="uq_deliverables_scope",
        ),
        UniqueConstraint("project_id", "doc_no", name="uq_deliverables_doc_no"),
    )
    deliverable_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.project_id"), index=True)
    deliverable_type: Mapped[str] = mapped_column(
        String(30),
        comment="DeliverableType：PIPE_LIST/EQUIP_LIST/CALC_BOOK/PUMP_DATASHEET/PSV_DATASHEET/"
                "HEAT_DATASHEET/VESSEL_DATASHEET/UTIL_SUMMARY/CHANGE_NOTICE/CUSTOM_REPORT",
    )
    scope_type: Mapped[str] = mapped_column(String(20), comment="PROJECT_ALL/UNIT/SUB_PROJECT/CUSTOM")
    scope_value: Mapped[str] = mapped_column(String(100), comment="ALL 或 '5000'/'ISBL'")
    parent_deliverable_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("deliverables.deliverable_id")
    )
    doc_no: Mapped[str] = mapped_column(String(200), index=True)
    doc_no_mode: Mapped[str] = mapped_column(String(20), comment="MANUAL/WORLEY_STD/CUSTOM")
    numbering_template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("numbering_templates.template_id")
    )
    segment_values_json: Mapped[dict | None] = mapped_column(JSONB)
    discipline_code: Mapped[str | None] = mapped_column(String(2))
    doc_identifier_code: Mapped[str | None] = mapped_column(String(3))
    sequence_no: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    current_rev: Mapped[str] = mapped_column(String(20), comment="A/B/0/1/AS-BUILT/X")
    version_purpose: Mapped[str] = mapped_column(
        String(40), comment="VersionPurpose 13 值，含 ISSUED_FOR_CHANGE"
    )
    sign_status: Mapped[DeliverableSignStatus] = mapped_column(
        Enum(DeliverableSignStatus, name="deliverablesignstatus", native_enum=True),
        nullable=False, default=DeliverableSignStatus.DRAFT, index=True,
    )
    matrix_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("signature_matrices.matrix_id"))
    # 客户批准 = 凭证代录（ADR-0007）
    customer_approval_date: Mapped[date | None] = mapped_column(Date)
    customer_approver_name: Mapped[str | None] = mapped_column(String(100))
    customer_approval_method: Mapped[str | None] = mapped_column(
        String(20), comment="EMAIL/LETTER/EDMS/SIGNED_DOC"
    )
    customer_approval_proxy_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, comment="代录人")
    customer_approval_proxy_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    customer_approval_attachment_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    customer_approval_is_proxy: Mapped[bool | None] = mapped_column(Boolean)


class DeliverableVersion(TimestampMixin, Base):
    __tablename__ = "deliverable_versions"
    version_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    deliverable_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deliverables.deliverable_id"), index=True
    )
    rev: Mapped[str] = mapped_column(String(20))
    version_purpose: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    record_snapshot_json: Mapped[dict] = mapped_column(JSONB, comment="记录ID+哈希汇总")
    signature_summary_json: Mapped[dict] = mapped_column(JSONB)
    customer_approval_date: Mapped[date | None] = mapped_column(Date)
    pdf_file_path: Mapped[str | None] = mapped_column(String(500))
    affected_status: Mapped[str | None] = mapped_column(
        String(10), comment="NONE/AFFECTED（快照哈希与当前不一致标记）"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DeliverableRecordBinding(Base):
    """快照绑定：仅 CHECKED 记录可绑（ADR-0012），record_hash 固化。"""
    __tablename__ = "deliverable_record_bindings"
    binding_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    deliverable_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deliverable_versions.version_id"), index=True
    )
    record_type: Mapped[str] = mapped_column(
        String(30), comment="PIPE_RESULT/PUMP_RESULT 等（多态）"
    )
    record_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    record_hash: Mapped[str] = mapped_column(String(64))
    old_record_hash_before_change: Mapped[str | None] = mapped_column(String(64))


class SignatureMatrix(TimestampMixin, Base):
    """签署矩阵（SUP-005 机制，V3.1 表34 新增入册）。"""
    __tablename__ = "signature_matrices"
    matrix_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    matrix_name: Mapped[str] = mapped_column(String(200))
    module: Mapped[str] = mapped_column(String(30), comment="* 表示全部")
    doc_type: Mapped[str] = mapped_column(String(30))
    version_purpose: Mapped[str] = mapped_column(String(40))
    steps_json: Mapped[list] = mapped_column(
        JSONB, comment='[{"step_order","sign_role","required","can_self_check","can_skip"}]'
    )
    status: Mapped[str] = mapped_column(String(20), comment="DRAFT/PENDING/ACTIVE/OBSOLETE")


class ProjectSignatureMatrixBinding(TimestampMixin, Base):
    __tablename__ = "project_signature_matrix_bindings"
    binding_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.project_id"), index=True
    )
    module: Mapped[str] = mapped_column(String(30))
    matrix_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("signature_matrices.matrix_id"), index=True
    )
```

- [ ] **Step 2: 其余 3 表**

`CustomerApprovalAttachment`（表36）：attachment_id PK、deliverable_version_id FK ✅ index、file_path ✅、file_name ✅、file_type String(10) ✅（PDF/JPG/PNG/EML）、file_size Integer ✅、uploaded_by Uuid ✅、uploaded_at ✅、file_hash String(64) ✅（SHA-256 防篡改）——不继承 TimestampMixin（自有 uploaded_*）。
`ChangeNoticeDetail`（表37，TimestampMixin）：detail_id PK、deliverable_id FK unique ✅（1:1）、change_type String(30) ✅（7 值）、reason Text ✅、triggered_by String(20) ✅（MANUAL/UPSTREAM_CHANGE）、source_record_type String(30) ❌。
`RecordChangeSnapshot`（表38，无 TimestampMixin）：snapshot_id PK、record_type String(30) ✅ index、record_id Uuid ✅ index、record_hash String(64) ✅、data_snapshot_json JSONB ✅（完整设计参数）、snapshot_reason String(20) ✅（BEFORE_CHANGE/BEFORE_STALE/BEFORE_DRAFT）、snapshot_source String(20) ✅（MANUAL_CHANGE/UPSTREAM_CHANGE/MANUAL_ROLLBACK）、created_at、created_by。

- [ ] **Step 3: 校验 + Commit**

```bash
uv run ruff check . && uv run mypy app/
git add pcs-backend && git commit -m "feat(db): deliverable domain 9 tables incl. signature matrices"
```

---

### Task 7: 横切 + 许可 + AI 预留模型（字典表43–53）

**Files:**
- Create: `pcs-backend/app/models/misc.py`；更新 `pcs-backend/app/models/__init__.py` 为全量导入（见 Task 2 Step 4）

**Interfaces:**
- Produces: `DataLineage`、`ProjectInputChecklist`、`AuditLog`、`SystemSetting`、`ReportDefinition`、`ReportExecutionLog`、`DocumentChunk`、`AiAuditLog`、`LicenseConfig`。（Supplier 已移 equipment.py，见 Task 5）

- [ ] **Step 1: 建模要点（字典逐字）**

- `DataLineage`（表43，哈希锚定）：lineage_id UUID PK；source_type String(30) ✅、source_id Uuid ✅、source_record_hash String(64) ✅；target_type/target_id/target_record_hash 同构 ✅；dependency_type String(30) ✅；field_name String(100) ✅；formula_version/config_version String(50) ❌；timestamp ✅。**无 source_version/target_version**。
- `ProjectInputChecklist`（表44）：input_id PK、project_id FK ✅、module/input_name/input_category/source_type/status ✅、input_value_json、verified_by/verified_at、assumption_reason、last_updated ✅。
- `AuditLog`（表46）：log_id PK、user_id ✅、module ✅、object_id String(64) ✅、action String(50) ✅（含 LICENSE_VIOLATION/CHANGE_ABANDONED/CHANGE_REVERSAL_APPROVED/RECORD_OBSOLETED/CUSTOMER_APPROVAL_PROXIED）、old_value/new_value JSONB、ip_address、remarks、timestamp ✅、hash String(64) ✅、**sign_role String(30)**、**sign_step Integer**（V3.0 新增两列）。
- `SystemSetting`（表48）：setting_id PK、setting_key ✅ unique、setting_value JSONB ✅、updated_by、updated_at ✅。
- `ReportDefinition`（表49）：report_def_id PK、report_name(200)/report_category/output_format ✅、data_sources_json/selected_fields_json JSONB ✅、filter_conditions_json/sort_by_json、max_rows Integer（默认 10000）、output_template_id FK→template_files、version String(50) ✅（报表定义仍用版本——配置资产）、shared_with/project_scope String(30) ✅、created_by/at、status。
- `ReportExecutionLog`（表50）：log_id PK、report_def_id FK ✅、report_def_version ✅、executed_by/executed_at ✅、filter_snapshot_json、row_count ✅、export_format ✅。
- `DocumentChunk`（表51）：chunk_id PK、document_id String(64) ✅、content Text ✅、vector_id、source、created_at ✅；**不建 embedding vector(1536) 列**——需 pgvector 扩展，P0 不引入（偏离记 STATUS）。
- `AiAuditLog`（表52）：log_id PK、user_id ✅、timestamp ✅、request_summary ✅（脱敏）、response_summary、model_version。
- `LicenseConfig`（表53，V3.1 新增域）：license_id PK、license_type String(10) ✅（FULL/DEMO/TRIAL）、max_projects Integer ✅、module_limits_json JSONB ✅（活记录计数口径 ADR-0011）、watermark_enabled Boolean ✅、watermark_text ✅、config_readonly ✅、equip_lib_settle_disabled ✅、workspace_types_allowed JSONB ✅、ai_enabled ✅、trial_start_date/trial_end_date Date ❌、created_at/updated_at。

- [ ] **Step 2: 校验 + Commit**

```bash
uv run ruff check . && uv run mypy app/
git add pcs-backend && git commit -m "feat(db): cross-cutting/license/AI-reserved models; DEVIATION: document_chunks.embedding(vector1536) deferred to P10 (no pgvector in P0)"
```

---

### Task 8: Alembic 初始化 + 全量迁移 + Schema 测试

**Files:**
- Create: `pcs-backend/alembic.ini`、`pcs-backend/alembic/env.py`、`pcs-backend/alembic/versions/0001_p0_schema.py`
- Test: `pcs-backend/tests/test_db_schema.py`

**Interfaces:**
- Consumes: `app.models`（全量表注册于 `Base.metadata`）、`get_settings().database_url`。
- Produces: `alembic upgrade head` 可从空库建全部表。

- [ ] **Step 1: init**

```bash
cd pcs-backend && uv run alembic init alembic
```

- [ ] **Step 2: alembic.ini** — `sqlalchemy.url` 留空（env.py 注入）。

- [ ] **Step 3: env.py 关键改动**

```python
from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base
import app.models  # noqa: F401  全量注册

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata
# offline/online 两分支保留模板默认，online 用 config
```

- [ ] **Step 4: 生成并校对迁移**

```bash
uv run alembic revision --autogenerate -m "p0 schema"
```

手写校对要点：autogenerate 顶部 `import sqlalchemy as sa` 后确认含**三个** PG 枚举（`recordsignstatus`/`streamsignstatus`/`deliverablesignstatus`）；确认无任何 `xxx_History` 表；确认无 `version` 列出现在业务记录表（pipe_classes.version/config_versions.version_code/report_definitions.version 三个**配置类**除外）；确认唯一约束：projects.project_no、streams(project_id,stream_name)、piping 仅 (project_id,line_no)、各记录表(project_id,tag_number)、deliverables 两组、users.username、system_settings.setting_key、change_notice_details.deliverable_id、**equipment_type_codes(project_id, type_code)**（V3.1 ADR-0023 复合约束）；**循环 FK**：projects↔workspaces 由 `use_alter=True` 化解（迁移应出现 ALTER TABLE add FK）。表数量预期 **53**（字典 V3.1 表清单），以 `len(Base.metadata.tables)` 实际打印核对，不符则停查。

- [ ] **Step 5: 执行迁移**

```bash
uv run alembic upgrade head && uv run alembic check
```
Expected: 无报错，alembic check 无新 diff。

- [ ] **Step 6: 写失败测试 test_db_schema.py**

```python
import os

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.db.base import Base
import app.models  # noqa: F401

DB_URL = os.environ.get("PCS_TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DB_URL, reason="需要 PCS_TEST_DATABASE_URL 指向空测试库"
)

EXPECTED_TABLES = {
    "projects", "streams", "stream_state_points",
    "config_assets", "config_versions", "config_approvals", "formula_definitions",
    "coefficient_tables", "template_files", "project_templates", "pipe_classes",
    "project_pipe_classes", "numbering_templates", "doc_no_sequences",
    "piping_results", "pump_results", "psv_results", "vessel_results", "heat_results",
    "cv_results", "flash_results", "pipe_network_results", "restriction_results",
    "flare_system_results", "cooling_tower_results", "psychro_results",
    "sep_equip_results", "filtration_results", "cost_est_results", "open_channel_results",
    "equipment_list", "equipment_type_codes", "equipment_lib", "suppliers",
    "deliverables", "deliverable_versions", "deliverable_record_bindings",
    "signature_matrices", "project_signature_matrix_bindings",
    "customer_approval_attachments", "change_notice_details", "record_change_snapshots",
    "data_lineage", "project_input_checklist", "workspaces", "audit_logs",
    "users", "system_settings",
    "report_definitions", "report_execution_logs",
    "document_chunks", "ai_audit_log", "license_configs",
}


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(DB_URL)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


def test_all_tables_created(engine) -> None:
    tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
    assert EXPECTED_TABLES <= tables
    assert len(tables) == 53, f"expected 53 tables, got {len(tables)}: {sorted(tables)}"


def test_no_history_tables(engine) -> None:
    tables = set(inspect(engine).get_table_names())
    assert not any(t.endswith("_history") for t in tables)


def test_no_version_column_on_record_tables(engine) -> None:
    cols = {c["name"] for c in inspect(engine).get_columns("pump_results")}
    assert "version" not in cols and "version_purpose" not in cols


def test_tag_lifetime_uniqueness(engine) -> None:
    uqs = {
        tuple(c["column_names"])
        for c in inspect(engine).get_unique_constraints("pump_results")
    }
    assert ("project_id", "tag_number") in uqs


def test_equipment_type_code_composite_pk(engine) -> None:  # V3.1 ADR-0023
    pk = inspect(engine).get_pk_constraint("equipment_type_codes")
    assert set(pk["constrained_columns"]) == {"project_id", "type_code"}
    uqs = {
        tuple(c["column_names"])
        for c in inspect(engine).get_unique_constraints("equipment_type_codes")
    }
    assert ("project_id", "type_code") in uqs
```

- [ ] **Step 7: 跑（针对 compose 的 PG，建独立测试库）**

```bash
docker compose -f ../docker-compose.yml exec -T postgres createdb -U pcs pcs_test 2>/dev/null || true
PCS_TEST_DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test \
  uv run pytest tests/test_db_schema.py -v
```
Expected: 4 PASS。

- [ ] **Step 8: Commit**

```bash
git add pcs-backend && git commit -m "feat(db): alembic full-schema migration, 53-table verification tests"
```

---

### Task 9: JWT + LDAP 认证 + auth API

**Files:**
- Create: `pcs-backend/app/core/security.py`、`pcs-backend/app/core/auth_ldap.py`、`pcs-backend/app/api/deps.py`、`pcs-backend/app/api/v1/auth.py`、`pcs-backend/app/schemas/auth.py`
- Test: `pcs-backend/tests/fakes.py`、`pcs-backend/tests/conftest.py`、`pcs-backend/tests/test_security.py`、`pcs-backend/tests/test_auth_api.py`、`pcs-backend/tests/test_deps.py`

（不建 schemas/common.py——P0 无共用响应模型，YAGNI；错误响应已在 core/errors.py 的 ErrorResponse。）

**Interfaces:**
- Produces:
  - `security.py`：`create_token(user: AuthUser, token_type: Literal["access","refresh"]) -> str`；`decode_token(token: str, expected_type: str) -> dict`（失败抛 `PcsError(code="AUTH_INVALID_TOKEN", status=401)`）
  - `auth_ldap.py`：`authenticate(username: str, password: str) -> AuthUser | None`（内部ldap3，可用 `connection_factory` 注入替换——测试用）；`map_groups_to_roles(groups: list[str], mapping: dict[str,str]) -> list[str]`
  - `AuthUser`（schemas/auth.py，Pydantic）：`user_id: str, username: str, display_name: str, roles: list[str], ad_groups: list[str]`
  - API：`POST /api/v1/auth/login` `{username,password}` → `TokenPair`；`POST /api/v1/auth/refresh` `{refresh_token}` → `TokenPair`；`GET /api/v1/auth/me`（受保护）；401 错误体走统一格式
  - `deps.py`：`get_current_user(request) -> AuthUser`（Bearer 解析）
  - MFA 预留（SPEC P0-AUTH-001）：JWT payload 留 `"mfa": None` 扩展位，P0 不校验

- [ ] **Step 1: 写失败测试 test_security.py**

```python
import pytest

from app.core.errors import PcsError
from app.core.security import create_token, decode_token
from app.schemas.auth import AuthUser

USER = AuthUser(
    user_id="u-1", username="designer01", display_name="设计员一",
    roles=["DESIGNER"], ad_groups=["DESIGNER_GROUP"],
)


def test_token_roundtrip() -> None:
    tok = create_token(USER, "access")
    claims = decode_token(tok, "access")
    assert claims["sub"] == "u-1" and claims["roles"] == ["DESIGNER"]


def test_wrong_type_rejected() -> None:
    tok = create_token(USER, "refresh")
    with pytest.raises(PcsError):
        decode_token(tok, "access")


def test_garbage_token_rejected() -> None:
    with pytest.raises(PcsError):
        decode_token("not-a-jwt", "access")


def test_expired_token_rejected() -> None:
    import datetime as dt

    from authlib.jose import JWT

    from app.core.config import get_settings

    payload = {
        "sub": "u-1", "type": "access",
        "exp": int((dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1)).timestamp()),
    }
    expired = JWT().encode({"alg": "HS256"}, payload, get_settings().secret_key).decode()
    with pytest.raises(PcsError):
        decode_token(expired, "access")
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run pytest tests/test_security.py -v
```
Expected: ImportError/FAIL。

- [ ] **Step 3: 实现 security.py（authlib.jose）**

```python
from typing import Any, Literal

from authlib.jose import JWT, JoseError

from app.core.config import get_settings
from app.core.errors import PcsError
from app.schemas.auth import AuthUser

_jwt = JWT()


def create_token(user: AuthUser, token_type: Literal["access", "refresh"]) -> str:
    import datetime as dt

    s = get_settings()
    minutes = (
        s.access_token_expire_minutes
        if token_type == "access"
        else s.refresh_token_expire_days * 24 * 60
    )
    header = {"alg": "HS256"}
    payload = {
        "sub": user.user_id, "username": user.username,
        "roles": user.roles, "type": token_type, "mfa": None,  # MFA 预留
        "exp": int((dt.datetime.now(dt.UTC) + dt.timedelta(minutes=minutes)).timestamp()),
        "iat": int(dt.datetime.now(dt.UTC).timestamp()),
    }
    return _jwt.encode(header, payload, s.secret_key).decode()


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    s = get_settings()
    try:
        claims = _jwt.decode(token, s.secret_key)
        claims.validate()
    except JoseError as e:
        raise PcsError("AUTH_INVALID_TOKEN", "invalid or expired token", 401) from e
    if claims.get("type") != expected_type:
        raise PcsError("AUTH_INVALID_TOKEN", f"expected {expected_type} token", 401)
    return dict(claims)
```

`schemas/auth.py`：

```python
from pydantic import BaseModel, Field


class AuthUser(BaseModel):
    user_id: str
    username: str
    display_name: str = ""
    roles: list[str] = Field(default_factory=list)
    ad_groups: list[str] = Field(default_factory=list)


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: AuthUser
```

- [ ] **Step 4: 跑 tests/test_security.py** → 3 PASS。

- [ ] **Step 5: auth_ldap.py**

```python
from typing import Protocol

import ldap3

from app.core.config import get_settings
from app.schemas.auth import AuthUser

VALID_ROLES = {
    "DESIGNER", "CHECKER", "REVIEWER", "APPROVER", "SYSADMIN",
    "PROCESS_CONTROLLER", "DATA_ADMIN",
}  # ApprovalRole 7 值（字典 V3.1）

# typing: from collections.abc import Callable, Protocol 顶部导入


def map_groups_to_roles(groups: list[str], mapping: dict[str, str]) -> list[str]:
    roles = {mapping[g] for g in groups if g in mapping}
    return sorted(roles & VALID_ROLES)


class ConnectionLike(Protocol):
    def bind(self) -> bool: ...


def _real_connection(dn: str, password: str) -> ldap3.Connection:
    server = ldap3.Server(get_settings().ldap_url, get_info=ldap3.NONE)
    return ldap3.Connection(server, user=dn, password=password, auto_bind=True)


def authenticate(
    username: str,
    password: str,
    connection_factory: Callable[[str, str], ConnectionLike] | None = None,
) -> AuthUser | None:
    s = get_settings()
    factory = connection_factory or _real_connection
    try:
        conn = factory(s.ldap_user_dn_template.format(username=username), password)
    except Exception:
        return None
    if not conn or (hasattr(conn, "bound") and not conn.bound):
        return None
    # 组提取：memberOf（真实 ldap3 Connection 有 search/response；fake 自带 groups 属性）
    groups = getattr(conn, "mock_groups", None)
    if groups is None:
        conn.search(
            s.ldap_base_dn, f"(cn={username})",
            attributes=["memberOf"],
        )
        groups = [
            e for entry in conn.entries for e in entry.memberOf.values
        ] if conn.entries else []
    roles = map_groups_to_roles(list(groups), s.group_role_map())
    return AuthUser(
        user_id=username, username=username, display_name=username,
        roles=roles, ad_groups=list(groups),
    )
```

- [ ] **Step 6: auth API + deps**

`app/api/v1/auth.py`：

```python
from fastapi import APIRouter

from app.core.auth_ldap import authenticate
from app.core.errors import PcsError
from app.core.security import create_token
from app.schemas.auth import AuthUser, LoginRequest, RefreshRequest, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])


def _pair(user: AuthUser) -> TokenPair:
    return TokenPair(
        access_token=create_token(user, "access"),
        refresh_token=create_token(user, "refresh"),
        user=user,
    )


@router.post("/login", response_model=TokenPair)
async def login(body: LoginRequest) -> TokenPair:
    user = authenticate(body.username, body.password)
    if user is None:
        raise PcsError("AUTH_INVALID_CREDENTIALS", "invalid username or password", 401)
    return _pair(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest) -> TokenPair:
    from app.core.security import decode_token

    claims = decode_token(body.refresh_token, "refresh")
    user = AuthUser(
        user_id=str(claims["sub"]), username=str(claims.get("username", "")),
        roles=list(claims.get("roles", [])), ad_groups=[],
    )
    return _pair(user)
```

`app/api/deps.py`：

```python
from typing import Annotated

from fastapi import Depends, Request

from app.core.errors import PcsError
from app.core.security import decode_token
from app.schemas.auth import AuthUser


def get_current_user(request: Request) -> AuthUser:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise PcsError("AUTH_NO_TOKEN", "missing bearer token", 401)
    claims = decode_token(auth.removeprefix("Bearer "), "access")
    return AuthUser(
        user_id=str(claims["sub"]), username=str(claims.get("username", "")),
        roles=list(claims.get("roles", [])), ad_groups=[],
    )


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
```

`app/api/__init__.py` 补回 auth 行（Task 1 注）。

`tests/fakes.py`：

```python
"""FakeLdapConnection：注入 authenticate(connection_factory=...)。"""


class FakeLdapConnection:
    def __init__(self, bind_ok: bool, groups: list[str] | None = None):
        self.bound = bind_ok
        self.mock_groups = groups or []

    def bind(self) -> bool:
        return self.bound


def fake_factory(bind_ok: bool, groups: list[str] | None = None):
    def _factory(dn: str, password: str) -> FakeLdapConnection:
        if not bind_ok:
            raise RuntimeError("invalid credentials")
        return FakeLdapConnection(bind_ok, groups)

    return _factory
```

`tests/test_auth_api.py`（monkeypatch 替换模块级 `_real_connection`，authenticate 的 factory 缺省即取它）：

```python
import pytest
from fastapi.testclient import TestClient

import app.core.auth_ldap as auth_ldap_mod
from app.main import create_app
from tests.fakes import fake_factory


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_login_ok_returns_tokens(client, monkeypatch):  # AUTH-T-001（+T-006 多组多角色）
    monkeypatch.setattr(
        auth_ldap_mod, "_real_connection",
        fake_factory(True, ["DESIGNER_GROUP", "CHECKER_GROUP"]),
    )
    resp = client.post(
        "/api/v1/auth/login", json={"username": "designer01", "password": "x"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]
    assert sorted(body["user"]["roles"]) == ["CHECKER", "DESIGNER"]


def test_login_bad_password_401(client, monkeypatch):  # AUTH-T-002
    monkeypatch.setattr(auth_ldap_mod, "_real_connection", fake_factory(False))
    resp = client.post("/api/v1/auth/login", json={"username": "u", "password": "bad"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_INVALID_CREDENTIALS"


def test_group_mapping_unit():  # AUTH-T-005（映射函数单测）
    from app.core.auth_ldap import map_groups_to_roles

    mapping = {"DESIGNER_GROUP": "DESIGNER", "ADMIN_GROUP": "SYSADMIN"}
    assert map_groups_to_roles(["DESIGNER_GROUP"], mapping) == ["DESIGNER"]
    assert map_groups_to_roles(["UNKNOWN_GROUP"], mapping) == []


def test_refresh_with_access_token_401(client):  # eng-review T-d：错型 token
    from app.core.security import create_token
    from app.schemas.auth import AuthUser

    user = AuthUser(user_id="u-1", username="u", display_name="u", roles=["DESIGNER"])
    access = create_token(user, "access")
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401
```

`tests/test_deps.py`（`GET /auth/me` 为受保护端点，auth.py 中追加 `@router.get("/me")` + `Depends(get_current_user)` 返回 CurrentUser）：

```python
import pytest
from fastapi.testclient import TestClient

import app.core.auth_ldap as auth_ldap_mod
from app.main import create_app
from tests.fakes import fake_factory


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_no_token_401(client):  # AUTH-T-003
    assert client.get("/api/v1/auth/me").status_code == 401


def test_invalid_token_401(client):  # AUTH-T-004
    resp = client.get(
        "/api/v1/auth/me",
        headers={"authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.bad.sig"},
    )
    assert resp.status_code == 401


def test_refresh_flow(client, monkeypatch):  # AUTH-T-008
    monkeypatch.setattr(
        auth_ldap_mod, "_real_connection", fake_factory(True, ["DESIGNER_GROUP"])
    )
    login = client.post(
        "/api/v1/auth/login", json={"username": "designer01", "password": "x"}
    ).json()
    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"authorization": f"Bearer {new_access}"})
    assert me.status_code == 200 and me.json()["username"] == "designer01"
```

`tests/conftest.py`（SPEC P0-AUTH-002 Mock 用户工厂——dependency_overrides 覆盖 get_current_user）：

```python
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import create_app
from app.schemas.auth import AuthUser


def make_user(user_id: str, username: str, roles: list[str]) -> AuthUser:
    return AuthUser(
        user_id=user_id, username=username, display_name=username,
        roles=roles, ad_groups=[f"{r}_GROUP" for r in roles],
    )


@pytest.fixture
def mock_designer():
    return make_user("test-designer-001", "designer01", ["DESIGNER"])


@pytest.fixture
def mock_checker():
    return make_user("test-checker-001", "checker01", ["CHECKER"])


@pytest.fixture
def designer_client(mock_designer):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: mock_designer
    return TestClient(app)
```

- [ ] **Step 7: 跑全部认证测试**

```bash
uv run pytest tests/test_security.py tests/test_auth_api.py tests/test_deps.py -v
```
Expected: AUTH-T-001/002/003/004/006/008 对应用例全 PASS。

- [ ] **Step 8: Commit**

```bash
git add pcs-backend && git commit -m "feat(auth): ldap bind + authlib jwt, login/refresh/me endpoints"
```

---

### Task 10: Mock 认证 + 生产禁用 + 测试 AD 容器

**Files:**
- Create: `pcs-backend/app/core/auth_mock.py`、`pcs-backend/app/api/v1/mock_auth.py`、`PCS/docker-compose.ad.yml`
- Test: `pcs-backend/tests/test_mock_auth.py`

**Interfaces:**
- Consumes: `create_token`、`AuthUser`、`get_settings().env`。
- Produces: `POST /api/v1/auth/mock-login` `{username, role}` → TokenPair（仅 dev/test 挂载）；`mock_login(username, role) -> AuthUser`（production 调用即抛 RuntimeError）。

- [ ] **Step 1: 失败测试 test_mock_auth.py**

```python
from fastapi.testclient import TestClient

from app.core.auth_mock import mock_login
from app.main import create_app


def test_mock_login_dev_ok():  # AUTH-T-005 角色直授
    c = TestClient(create_app())
    resp = c.post("/api/v1/auth/mock-login", json={"username": "designer01", "role": "DESIGNER"})
    assert resp.status_code == 200
    assert resp.json()["user"]["roles"] == ["DESIGNER"]


def test_mock_login_invalid_role_400():  # eng-review T-a：非法角色
    c = TestClient(create_app())
    resp = c.post("/api/v1/auth/mock-login", json={"username": "x", "role": "SUPERUSER"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "AUTH_INVALID_ROLE"


def test_mock_disabled_in_production(monkeypatch):  # AUTH-T-007
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ENV", "production")
    get_settings.cache_clear()
    try:
        c = TestClient(create_app())
        resp = c.post(
            "/api/v1/auth/mock-login", json={"username": "x", "role": "DESIGNER"}
        )
        assert resp.status_code in (403, 404)
        import pytest

        with pytest.raises(RuntimeError):
            mock_login("x", "DESIGNER")
    finally:
        monkeypatch.delenv("ENV", raising=False)
        get_settings.cache_clear()


def test_secret_key_default_rejected_in_production(monkeypatch):  # eng-review Issue 1
    import pytest

    from app.core.config import assert_secret_key_configured, get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ENV", "production")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            assert_secret_key_configured()
    finally:
        monkeypatch.delenv("ENV", raising=False)
        get_settings.cache_clear()
```

注：production 下 `create_app()` 还会因 include_router 无 mock 而天然 404；mock_login 内部再查 `settings.is_production` 抛 RuntimeError 作为启动自检同源逻辑。启动自检走 **lifespan**（不用已弃用的 on_event）——Step 3 同时在 main.py 的 lifespan 内注入：

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app.core.auth_mock import assert_mock_not_enabled
    from app.core.config import assert_secret_key_configured

    assert_mock_not_enabled(app)  # production 且路由表含 mock-login → RuntimeError
    assert_secret_key_configured()  # production 禁默认值/过短 SECRET_KEY（eng-review Issue 1）
    yield
```

`app/core/config.py` 追加：

```python
def assert_secret_key_configured() -> None:
    """production 启动自检：SECRET_KEY 不得为默认值或短于 32 字节。"""
    s = get_settings()
    if s.is_production and (
        s.secret_key == "dev-secret-key-not-for-production--" or len(s.secret_key) < 32
    ):
        raise RuntimeError("SECRET_KEY must be a strong value (>=32 chars) in production")
```

- [ ] **Step 2: 跑测试确认失败** → ImportError。

- [ ] **Step 3: 实现 auth_mock.py + mock_auth.py**

`app/core/auth_mock.py`：

```python
from app.core.config import get_settings
from app.core.errors import PcsError
from app.schemas.auth import AuthUser

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.errors import PcsError
from app.schemas.auth import AuthUser

MOCK_ROLES = [
    "DESIGNER", "CHECKER", "REVIEWER", "APPROVER", "SYSADMIN",
    "PROCESS_CONTROLLER", "DATA_ADMIN",
]


def mock_login(username: str, role: str) -> AuthUser:
    s = get_settings()
    if s.is_production:
        raise RuntimeError("mock auth must never run in production")
    if role not in MOCK_ROLES:
        raise PcsError("AUTH_INVALID_ROLE", f"role must be one of {MOCK_ROLES}", 400)
    return AuthUser(
        user_id=f"mock-{username}", username=username, display_name=f"{username}(mock)",
        roles=[role], ad_groups=[f"{role}_GROUP"],
    )


def assert_mock_not_enabled(app: FastAPI) -> None:
    """production 启动自检：mock-login 路由不得存在于路由表。"""
    if get_settings().is_production:
        paths = {r.path for r in app.routes}
        if "/api/v1/auth/mock-login" in paths:
            raise RuntimeError("mock auth must never run in production")
```

`app/api/v1/mock_auth.py`：

```python
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.auth_mock import mock_login
from app.core.security import create_token
from app.schemas.auth import AuthUser, TokenPair

router = APIRouter(prefix="/auth", tags=["auth-mock"])


class MockLoginRequest(BaseModel):
    username: str
    role: str


@router.post("/mock-login", response_model=TokenPair)
async def mock_login_endpoint(body: MockLoginRequest) -> TokenPair:
    user = mock_login(body.username, body.role)
    return TokenPair(
        access_token=create_token(user, "access"),
        refresh_token=create_token(user, "refresh"),
        user=user,
    )
```

- [ ] **Step 4: docker-compose.ad.yml（Samba 测试域）**

```yaml
services:
  samba-ad:
    image: nowsci/samba-domain
    environment:
      DOMAIN: TEST.LOCAL
      ADMIN_PASSWORD: Test@123
    ports: ["389:389", "636:636"]
    volumes: [ad-data:/var/lib/samba]
volumes:
  ad-data:
```

（容器启动后手工建 5 账号 5 组——nowsci 镜像无自动 provisioning，本地集成测试时按镜像文档 `samba-tool user add`；P0 验收只需容器可起、LDAP 端口通。）

- [ ] **Step 5: 跑测试 + 容器冒烟**

```bash
uv run pytest tests/test_mock_auth.py -v
docker compose -f docker-compose.ad.yml up -d && sleep 20 \
  && docker compose -f docker-compose.ad.yml ps
```
Expected: 2 PASS；samba 容器 running（拉不到镜像 → 记 buglog，标注"内网镜像待 IT"，不阻塞）。

- [ ] **Step 6: Commit**

```bash
git add pcs-backend docker-compose.ad.yml && git commit -m "feat(auth): mock login for dev/test, production self-check, samba test domain compose"
```

---

### Task 11: 前端脚手架

**Files:**
- Create: `pcs-frontend/`（Vite 模板全量 + 下列定制）
- Modify: `package.json`（React 18 / Router v6 锁版）、`vite.config.ts`、`.env.development`、`.env.production`

**Interfaces:**
- Produces: `npm run dev`（5173，/api 代理 8000）；`npm run build` 成品；`src/services/api.ts` 导出 `apiFetch(path, init?) -> Promise<Response>`（自动附 Bearer、401 时静默 refresh 一次重试、再失败登出跳 /login）。

- [ ] **Step 1: 模板 + 锁版安装**

```bash
npm create vite@latest pcs-frontend -- --template react-ts
cd pcs-frontend
npm i react@18 react-dom@18 && npm i -D @types/react@18 @types/react-dom@18
npm i antd@5 zustand react-router-dom@6
```

- [ ] **Step 2: 目录 + vite.config.ts**

```
src/{pages,components,services,stores,types,utils,hooks}/
```

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
});
```

- [ ] **Step 3: env 文件**

`.env.development`：

```
VITE_API_BASE_URL=/api/v1
VITE_ENABLE_MOCK_AUTH=true
```

`.env.production`：

```
VITE_API_BASE_URL=/api/v1
VITE_ENABLE_MOCK_AUTH=false
```

- [ ] **Step 4: 验证 + Commit**

```bash
npm run build && npm run lint
git add pcs-frontend && git commit -m "feat(frontend): vite react18-ts scaffold, antd5, proxy config"
```

---

### Task 12: 登录页 + 主布局 + 路由 + 令牌内存存取

**Files:**
- Create: `pcs-frontend/src/types.ts`、`src/stores/authStore.ts`、`src/services/api.ts`、`src/pages/LoginPage.tsx`、`src/pages/HomePage.tsx、`src/components/AppLayout.tsx`、`src/App.tsx`、改 `src/main.tsx`

**Interfaces:**
- Consumes: 后端 `/api/v1/auth/login`、`/auth/refresh`、`/auth/mock-login`、`/health`。
- Produces: `useAuthStore`（`{user, accessToken, refreshToken, login(), mockLogin(), logout()}`——Zustand 内存，无 persist）。

- [ ] **Step 1: types.ts + authStore.ts**

```typescript
// src/types.ts
export interface AuthUser {
  user_id: string;
  username: string;
  display_name: string;
  roles: string[];
  ad_groups: string[];
}
export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: AuthUser;
}
```

```typescript
// src/stores/authStore.ts —— 仅内存，不 persist（SPEC 3.3.2）
import { create } from "zustand";
import type { AuthUser, TokenPair } from "../types";

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  setTokens: (p: TokenPair) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  setTokens: (p) =>
    set({ user: p.user, accessToken: p.access_token, refreshToken: p.refresh_token }),
  logout: () => set({ user: null, accessToken: null, refreshToken: null }),
}));
```

- [ ] **Step 2: services/api.ts（静默刷新一次）**

```typescript
import { useAuthStore } from "../stores/authStore";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = useAuthStore.getState().accessToken;
  const resp = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (resp.status === 401 && useAuthStore.getState().refreshToken) {
    const refreshed = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: useAuthStore.getState().refreshToken }),
    });
    if (refreshed.ok) {
      useAuthStore.getState().setTokens(await refreshed.json());
      return apiFetch(path, init); // 重试一次
    }
    useAuthStore.getState().logout();
  }
  return resp;
}
```

- [ ] **Step 3: LoginPage（antd Form + dev 角色 Select）**

```tsx
// src/pages/LoginPage.tsx
import { Button, Form, Input, Select, message } from "antd";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../services/api";
import { useAuthStore } from "../stores/authStore";
import type { TokenPair } from "../types";

const MOCK = import.meta.env.VITE_ENABLE_MOCK_AUTH === "true";
const ROLES = ["DESIGNER", "CHECKER", "REVIEWER", "APPROVER", "SYSADMIN"];

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const setTokens = useAuthStore((s) => s.setTokens);

  const login = async (v: { username: string; password: string; role?: string }) => {
    setLoading(true);
    try {
      const path = v.role ? "/auth/mock-login" : "/auth/login";
      const body = v.role ? { username: v.username, role: v.role } : v;
      const resp = await apiFetch(path, { method: "POST", body: JSON.stringify(body) });
      if (!resp.ok) {
        message.error("登录失败：用户名或密码错误");
        return;
      }
      setTokens((await resp.json()) as TokenPair);
      navigate("/");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", justifyContent: "center", paddingTop: "10vh" }}>
      <Form onFinish={login} style={{ width: 360 }}>
        <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
          <Input placeholder="域账号" />
        </Form.Item>
        <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
          <Input.Password placeholder="密码" />
        </Form.Item>
        {MOCK && (
          <Form.Item name="role" initialValue="DESIGNER">
            <Select placeholder="Mock 角色（仅开发）" options={ROLES.map((r) => ({ value: r, label: r }))} />
          </Form.Item>
        )}
        <Button type="primary" htmlType="submit" block loading={loading}>
          登录
        </Button>
      </Form>
    </div>
  );
}
```

- [ ] **Step 4: AppLayout + HomePage + App 路由**

```tsx
// src/components/AppLayout.tsx
import { Layout, Menu, Button, Space, Typography } from "antd";
import { Outlet, useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";

export default function AppLayout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Layout.Sider>
        <Menu theme="dark" mode="inline" selectedKeys={[]} items={[{ key: "home", label: "首页（占位）" }]} />
      </Layout.Sider>
      <Layout>
        <Layout.Header style={{ background: "#fff", padding: "0 24px" }}>
          <Space style={{ float: "right" }}>
            <Typography.Text>{user?.username ?? ""}</Typography.Text>
            <Button onClick={() => { logout(); navigate("/login"); }}>退出</Button>
          </Space>
        </Layout.Header>
        <Layout.Content style={{ margin: 24 }}>
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
```

```tsx
// src/pages/HomePage.tsx
import { Empty } from "antd";
export default function HomePage() {
  return <Empty description="PCS —— 功能建设中（P1+）" />;
}
```

```tsx
// src/App.tsx
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import { useAuthStore } from "./stores/authStore";

function RequireAuth({ children }: { children: JSX.Element }) {
  const token = useAuthStore((s) => s.accessToken);
  return token ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<RequireAuth><AppLayout /></RequireAuth>}>
          <Route index element={<HomePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
```

`main.tsx` 去掉模板冗余 CSS/StrictMode 包裹 App 即可（保留 StrictMode）。删除模板自带 `App.css` 引用。

- [ ] **Step 5: 验证（P0-FE-001 验收）**

```bash
npm run dev &   # 浏览器/curl 验证 http://localhost:5173/login 显示登录页
npm run build && npm run lint
```
Expected: dev 无控制台错误；build/lint 成功。

- [ ] **Step 6: Commit**

```bash
git add pcs-frontend && git commit -m "feat(frontend): login page with mock role select, app layout, in-memory token store"
```

---

### Task 13: 联调验证 + 收尾

**Files:**
- Modify: `CLAUDE.md`（追加 P0 开发规范段，保留 OpenWolf 段）
- Modify: `.wolf/STATUS.md`（用 /handoff 重新生成）、`.wolf/buglog.json`（如有 bug）

**Interfaces:**
- Consumes: 全部前置任务。

- [ ] **Step 1: 全链路**

```bash
# 终端1: docker compose up -d && cd pcs-backend && uv run alembic upgrade head \
#        && uv run uvicorn app.main:app --reload
# 终端2: cd pcs-frontend && npm run dev
curl -s localhost:8000/api/v1/health
curl -s -X POST localhost:8000/api/v1/auth/mock-login \
  -H 'Content-Type: application/json' -d '{"username":"designer01","role":"DESIGNER"}' | head -c 300
```
浏览器 5173/login → Mock 角色登录 → 进入主布局。Expected: 全通。

- [ ] **Step 2: 质量门**

```bash
cd pcs-backend && uv run ruff check . && uv run mypy app/ \
  && uv run pytest tests/ -v --cov=app --cov-report=term-missing
```
Expected: 零 error、全部 PASS、app/core 覆盖 ≥80%（整体不足 80% 记录于 STATUS，骨架层 models 无逻辑不计目标——如实报告）。

- [ ] **Step 3: CLAUDE.md 追加**（SPEC-P0 §3.2.6 内容：技术栈/编码规范/常用命令/架构约定，中文，追加到现有 OpenWolf 段之后）。其中架构约定**必须包含** FORMAL 项目运行时创建顺序（循环 FK 的蛋鸡问题）：

```
FORMAL 项目创建顺序：Workspace(project_id=NULL) → Project(workspace_id=ws) → 回填 Workspace.project_id
```

- [ ] **Step 4: 收尾**

bug 全部记 `.wolf/buglog.json`（error_message/root_cause/fix/tags）。执行 `/handoff` 重生成 STATUS.md（勾掉 P0 三条验收），遗留问题区记入 **Known Deviations**：
- `document_chunks.embedding vector(1536)` 推迟至 P10（P0 未引入 pgvector 扩展）
- FORMAL 项目创建顺序约定如上（运行时契约，非 Schema 缺陷）

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "chore: P0 acceptance verified, CLAUDE.md dev conventions, handoff"
```

---

## 范围外（明确不做，P0 后续）

- **无状态 refresh token 7 天内不可吊销**（eng-review Issue 2 已知限制）：logout 仅清前端内存，无黑名单/token_version。P0 内部部署（HTTPS+内存令牌）风险可接受；P1 在 users 表加 token_version 列并写入 JWT claim 校验。
- CI/CD 流水线（SPEC-P0 §3.2.5）：**用户裁决不做**——单人开发无需求，多人协作时再作为新需求提出（eng-review 2026-08-29）。质量门由 Task 13 本地执行替代。
- Samba 容器内 5 账号/5 组自动 provisioning（镜像能力限制，本地手工 samba-tool）。
- Golden Test（P0-OPEN-004，P4 提供）。

## 表数量核对表（= 字典 DICT-ALL-003 V3.1 §2 总览，迁移完成后核对）

| 域 | 表 |
|---|---|
| 项目与物流 (3) | projects, streams, stream_state_points |
| 配置层 (11) | config_assets, config_versions, config_approvals, formula_definitions, coefficient_tables, template_files, project_templates, pipe_classes, project_pipe_classes, numbering_templates, doc_no_sequences |
| 计算模块 (16) | flash, piping, pipe_network, pump, psv, flare_system, vessel, sep_equip, heat, cv, restriction, cooling_tower, psychro, open_channel, filtration, cost_est (_results) |
| 交付物层 (6) | deliverables, deliverable_versions, deliverable_record_bindings, signature_matrices, project_signature_matrix_bindings, customer_approval_attachments |
| 变更管理 (2) | change_notice_details, record_change_snapshots |
| 集成层 (4) | equipment_list, equipment_type_codes, equipment_lib, suppliers |
| 流程与横切 (6) | data_lineage, project_input_checklist, workspaces, audit_logs, users, system_settings |
| 报表层 (2) | report_definitions, report_execution_logs |
| AI 预留 (2) | document_chunks, ai_audit_log |
| 许可 (1) | license_configs |
| **合计** | **53** |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | 未运行（范围门在 eng-review Step 0 裁决：A 全量） |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | 未运行 |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | **CLEAR (PLAN)** 2026-08-29 | 8 issues，0 critical gaps，0 unresolved；全部裁决落计划（1A 密钥自检/2A 令牌吊销声明/3A 双图/4A 错误信封补全/5A TaggedRecordMixin/6A 四分支补测/7A 前端测试 TODO/8A GIN 推迟）；CI/CD 裁决不做（单人开发） |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | 未运行（P0 仅登录页+空布局） |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | 未运行 |

- **UNRESOLVED:** 0
- **VERDICT:** **ENG CLEARED — ready to implement**（延后工作见 `TODOS.md` 3 项）
