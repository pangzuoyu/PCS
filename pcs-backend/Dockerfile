# PCS 后端**生产镜像**（P10-C · T0-1 · TODO-163 的容器侧前提）
#
# ## 这个镜像解决什么
#
# ① **`flock`**（`util-linux`）⇒ ⇒ compose 的 `migrate` / `seed` 两个
#    **一次性写者**要抢**同一把车道锁**（`pcs-backend/.tmp/lane.lock`）
#    ⇒ ⇒ 否则直接 `docker compose run --rm seed` 能**绕过**宿主侧的锁
#    ⇒ ⇒ 与跑着的 PG 车道**并发**建 schema ⇒ ⇒ DDL 互相等锁 ⇒ ⇒
#    表现是「**偶发卡住**」（不是报错 ⇒ 极难定位）。
#    ⇒ ⇒ 见 `docs/superpowers/plans/2026-11-23-p10-c-deploy-observability.md`。
#
# ② **预装依赖**（`uv sync --frozen`）⇒ ⇒ 容器**起得来不靠网络**
#    ⇒ ⇒ 部署时不需要「进容器再装一遍」。
#
# ## ⚠️ **不装 `fonts-noto-cjk`**（PDF 渲染的坑）
#
# `reportlab` 要求 TrueType **轮廓** ⇒ ⇒ apt 的 `fonts-noto-cjk` 装出来是
# `.ttc` + CFF 轮廓 ⇒ ⇒ 报 `TTFError: postscript outlines are not supported`
# ⇒ ⇒ 真正管用的是**宿主机**的 `pcs-backend/fonts/NotoSansSC-Regular.ttf`
# （`uv run python scripts/build_report_font.py` 生成 · gitignore）
# ⇒ ⇒ ⇒ **装进镜像反而制造第二个坏候选** ⇒ ⇒ 不装。
#
# ## ⚠️ **pypi.org 本机不可达** ⇒ ⇒ 指阿里云镜像
#
# `UV_INDEX_URL` 默认走阿里云 ⇒ ⇒ 与宿主 `~/.config/pip/pip.conf` 一致
# ⇒ ⇒ `uv.lock` 里的哈希对同一份包不变 ⇒ ⇒ `--frozen` 仍然成立。
#
# ## 用法
#
#     docker build -t pcs-backend:local pcs-backend
#     docker run --rm -p 8000:8000 --env-file pcs-backend/.env pcs-backend:local
#
# ⚠️ 源码 baked in ⇒ ⇒ **改代码要重新构建** ⇒ ⇒ 日常开发仍用
# `docker-compose.yml` 里的**源码挂载**（本镜像也可只当「带 flock 的
# uv 环境」用 ⇒ ⇒ 挂载覆盖 `/app` 即可）。
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

#: pypi 镜像（宿主机同款 ⇒ ⇒ 与 `uv.lock` 的哈希一致）
ARG UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

ENV UV_INDEX_URL=${UV_INDEX_URL} \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_CACHE_DIR=/opt/uvcache \
    UV_HTTP_TIMEOUT=600 \
    UV_HTTP_RETRIES=10 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:${PATH}"

# `flock`（util-linux）⇒ ⇒ 车道锁
#
# ⚠️ **先看有没有**：Debian 的 `util-linux` 是 **priority: required** ⇒ ⇒
#    slim 基础镜像**通常自带** `flock` ⇒ ⇒ ⇒ **不必 apt** ⇒ ⇒ 构建不碰网络
#    （实测：apt 拉那个 8.8 MB 的 `Packages` 会**反复失败重试** ⇒ ⇒ 卡几分钟）。
# ⚠️ 万一没有 ⇒ ⇒ 再 apt（**换阿里云源** + **带重试** ⇒ ⇒ 镜像源抖一下不必
#    重跑整个构建）。
RUN set -eux; \
    if ! command -v flock >/dev/null 2>&1; then \
      printf 'deb https://mirrors.aliyun.com/debian/ bookworm main\n\
deb https://mirrors.aliyun.com/debian/ bookworm-updates main\n\
deb https://mirrors.aliyun.com/debian-security/ bookworm-security main\n' \
        > /etc/apt/sources.list; \
      rm -f /etc/apt/sources.list.d/debian.sources; \
      for i in 1 2 3; do \
        apt-get update && \
        apt-get install -y --no-install-recommends util-linux ca-certificates && \
        break; \
        echo "apt 第 $i 次失败 ⇒ ⇒ 重试"; sleep 5; \
      done; \
      rm -rf /var/lib/apt/lists/*; \
    fi; \
    command -v flock

WORKDIR /app

# ⚠️ **先拷源码**（生产镜像 = 源码 baked in）
# ⚠️ ⚠️ **源码必须先于 `uv sync`** —— hatchling 的 `force-include` 要读
#    `app/services/psychro/data/behr_coefficients.json`（实测：先 sync
#    ⇒ ⇒ FileNotFoundError: Forced include not found）。
COPY . /app

# ⚠️ **装项目本体** ⇒ ⇒ 容器内 `uv run --frozen` **不需要**构建后端
# ⇒ ⇒ ⇒ 也不碰网络（hatchling 已在镜像里 ⇒ ⇒ 不用现装）。
# ⚠️ **但挂载源码时不能被它盖住** ⇒ ⇒ `PYTHONPATH=/app`（见上面 ENV）
# ⇒ ⇒ ⇒ PYTHONPATH 排在 site-packages **之前** ⇒ ⇒ ⇒ 挂载的源码优先 ✔
RUN uv sync --frozen --no-dev

# 非 root 运行（生产镜像的基线）
#
# ⚠️ **删掉 uv 缓存** ⇒ ⇒ ① 镜像小 ② `chown -R` 快（缓存里是上万个文件
# ⇒ ⇒ ⇒ 实测 `chown -R /opt/uvcache` 要好几分钟）⇒ ⇒ ⇒ 运行时用不到它。
RUN rm -rf /opt/uvcache \
 && useradd --create-home --uid 10001 pcs \
 && chown -R pcs:pcs /app /opt/venv
USER pcs

EXPOSE 8000

# ⚠️ **不用 `uv run`** ⇒ ⇒ venv 已装好 ⇒ ⇒ 启动**不碰网络**
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
