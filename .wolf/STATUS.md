---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1200
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-11-25（第 49 轮：
> **TODO-210 落地** —— D1 模板默认单位制 + D3 BEDD 默认值落库 · SPEC V2.23）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done（第 49 轮 · **TODO-210**（D1 + D3 落库 · 小批）· 2026-11-25）

**两条人裁落地**（§7.10.6 的 D1 / D3 · 上一轮只裁规则、本轮落实现）：

- **D1 · 模板的默认单位制 = 「默认值」** ⇒ ⇒ ⇒ 用户显式选过 ⇒ ⇒ ⇒ **不覆盖**
  ⇒ ⇒ ⇒ 「用户动没动过」**由前端判定**（向导的 antd Form `onValuesChange`）
  ⇒ ⇒ ⇒ 契约 `POST /projects/{id}/apply-template` 的 body 加
  `unit_system_source: 'FORM' | 'TEMPLATE'`（**默认 `FORM`** = 保守：不动用户的值）
  ⇒ ⇒ ⇒ **后端不猜**（猜错 = 静默推翻用户的显式选择 ⇒ ⇒ 本仓最恨的那类事故）
  ⇒ ⇒ ⇒ 两者不一致 ⇒ ⇒ ⇒ 向导第 4 步**明确告知**（不静默）。
- **D3 · 模板的 BEDD 默认值** ⇒ ⇒ ⇒ apply **只填空缺**（用户已填的不动）
  ⇒ ⇒ ⇒ 与「输入清单」**完全同款**（按 key 幂等）⇒ ⇒ ⇒ 重复 apply **不丢用户数据**
  ⇒ ⇒ ⇒ 字段路径**对着 `BEDD_FIELDS` 校验** ⇒ ⇒ ⇒ 不认识的路径 ⇒ ⇒ ⇒
  **422 `TEMPLATE_BEDD_DEFAULTS_INVALID`**（不是静默丢弃）。

**两个模板默认值各占一列**（`project_templates.unit_system` VARCHAR(2) 可空 +
CHECK `ck_project_templates_unit_system` 与 `projects.unit_system` **同一个词表**
· `project_templates.bedd_defaults_json` JSONB 可空）⇒ ⇒ ⇒ ⚠️ **不能塞进
`default_config_json`** ⇒ ⇒ ⇒ 那里只有 7 段的 pydantic 模型 ⇒ ⇒ ⇒ ⇒ 多出来的键
会被**静默丢弃**（= bug-2210 同款）⇒ ⇒ ⇒ 迁移 **`p10_007`**（**全可空** ⇒ 存量行
不需回填 ⇒ 行为与迁移前**完全一致**）。

**车道**：后端默认 **6193**（+9）· PG **48**（新增 `ck_project_templates_unit_system`
的真 PG 违例）· 前端 typecheck/lint clean · 前端 **1149**（+3）· `alembic check`
**两库各一进程** exit 0（都 `p10_007 head`）· 裸载荷棘轮 **71 未涨** · 迁移幂等 RC 0
⇒ ⇒ ⇒ **浏览器实测拿到线上请求体级别的证据**（动过 ⇒ `"unit_system_source":"FORM"`；
没动 ⇒ `"TEMPLATE"`）⇒ ⇒ ⇒ **CRITICAL/HIGH 0 条**。

## ✅ Done（第 48 轮 · **P10-K**（SPEC §7.5 项目向导 · 28 个任务）· 2026-11-25）

**向导从占位页变成真流程**（4 步：建项目 → 项目人员 → 选模板 → 确认）⇒ ⇒ ⇒ ⚠️
**BEDD 必须在项目建完后录**（第 4 步「去项目录 BEDD」**深链**，不嵌表单）⇒ ⇒ ⇒ ⚠️
第 2/3 步失败 ⇒ ⇒ ⇒ **保留项目（DRAFT）+ 明确告知 + 两个出口**（不引入删除能力）
⇒ ⇒ ⇒ ⚠️ `/wizard` **挪进 admin 组**。
**三件今天做不到的事落地**：① **项目两态**（DRAFT/ACTIVE · **不是状态机** · 只单向）
② **单位制切换**（存储**恒 canonical(SI)** · 换算**只在控件边界** · ⚠️ **因子由后端下发**
⇒ 前端**没有换算表**）③ **项目模板**（列表 + 应用 + 发布语义 + seed · ⚠️ **命名响应
模型**（裸字段基线恰好顶满 71）· ⚠️ `record_approval` ↔ `signature_matrix` **互斥**
⇒ seed 种**两条** ⇒ ⚠️ **只替「自动绑的默认」** · 同一事务 + 幂等）。
**前端另修四处「点进去才发现」**：mock 零 `http.put` handler · 漂移守卫的 4 元组正则 ·
`unit_system` 自由文本 · mock 建的项目查不到。

## ✅ Done（第 47 轮 · **P10-J · T1**（公司级模板执行时选项目 · TODO-177）· 2026-11-25）

scope 解析**收在端点一处** · 判定顺序**不重排既有行为**（不一致 400 / 没选 400 /
授权 404 `PROJECT_NOT_FOUND`）⇒ ⇒ 入队与快照都传**解析后的 scope** ⇒ ⇒ 产出**有归属**。
⚠️ 前端：公司级模板才出现「选项目」下拉（必选无默认）· 候选源**按角色分** ·
**不复用** `useProjectScope` 那个并集 · 选择是**局部 state**。
⚠️ 建定义时拒「公司级 + 主源无 `project_id` 列」⇒ ⇒ 另给可区分的码。
契约：可选 `project_id` ⇒ ⇒ **三份都滚**。SPEC §7.18.2 + **V2.20** · **ADR-0051**。

## ✅ Done（第 43~46 轮 · 2026-11-23~24）

P10-J·T2「打回」（**不是新状态** ⇒ 9 态机不改）· P10-C T0/T1（容器侧同 inode 车道锁
⇒ TODO-163 闭 · 遗留账号迁移 ⇒ TODO-137 闭）· P10-I·T2（404 文案**逐字同形** ⇒
存在性不可枚举 · 124 处零影响）⇒ ⇒ 细节查 `git log`。

---

## 🚀 Next quest

1. ✅ P10-C · ✅ 8 条待裁项裁完 · ✅ P10-J·T2 · ✅ 两份计划批准
2. ✅ P10-J·T1（`5fc7b7e0`）⇒ **TODO-177 关闭** · ✅ P10-K（`ecede79f`）⇒ 28 任务全完成
   ⇒ ⇒ ⚠️ **SPEC 版本号从 V2.24 起算**（V2.23 已被 TODO-210 占用）
   ⇒ ⇒ ⚠️ 裸载荷棘轮**仍顶满 71** ⇒ ⇒ 下一批新增端点**照样**必须用命名响应模型
   （TODO-209 是**常设纪律**，仍开着）
3. ✅ **TODO-210 落地**（第 49 轮）⇒ ⇒ **§7.10.6 的 11 项全部已落**（SPEC **V2.23**）
   ⇒ ⇒ ⇒ ⚠️ **D2**（「默认模块启用状态」）已**划掉** ⇒ 归 license 级 ⇒ 若要项目级
   ⇒ **另开一批**（新功能 + 权限口径）
4. ⏭ **下一批 = 无既定计划** ⇒ ⇒ ⇒ 待用户定（可考虑：**TODO-206** 模板发布流程 ·
   **TODO-207** `nulls_not_distinct` 的其余表 · **TODO-208** admin 候选腿的浏览器实测
   · **TODO-137** 遗留账号迁移的部署前置）
5. **推送**：本轮提交**已授权 ⇒ 已推**

---

## Context

- main。**不要建 worktree** · **不要 `git checkout <commit> --detach`**。**不得擅自 push**。
  `.wolf/*` 里 `anatomy.md` / `memory.md` / `anatomy-index.json` 由 hook 维护。
- ⚠️ **每轮开工先查残留**：`fuser -v pcs-backend/.tmp/lane.lock` ·
  `pgrep -af "uvicorn app.main:app"` · `ss -ltnp | grep 5173`。
  ⚠️ **PG 车道被占 ⇒ 脚本直接 FAIL**（`flock -n`）⇒ ⇒ 先 `TaskStop` 掉旧的后台车道再跑。
- ⚠️ **默认车道零连真 PG** ⇒ ⇒ 跑 `pg` 用例**必须**走 `bash scripts/pytest_pg.sh`（**唯一入口**
  · 需 redis 起着）。
- ⚠️ **`.env` 口令不要写命令行** ⇒ 用 `dotenv_values('.env')` **进程内**派生 URL
  ⇒ ⇒ **一库一个进程**（alembic settings 是 pydantic 缓存实例）⇒ ⇒ **退出码是 255 不是 1**。
- ⚠️ **antd Select 的 placeholder 不是 `<input placeholder>`** ⇒ ⇒ 用
  `.ant-select-selection-placeholder` 的文本；驱动下拉照
  `tests/components/common/ProjectSelector.test.tsx`（`mouseDown(.ant-select-selector)`）。
  ⚠️ 按钮带图标 ⇒ 可访问名含图标 aria-label ⇒ ⇒ 用**正则**不用全等。
- ⚠️ **子代理 Bash 会挂起** ⇒ 派发审阅/实现子代理**只给 Read/Grep**。
- ⚠️ **后台任务容易被杀** ⇒ 跑长车道 ⇒ ⇒ ⇒ 用 `setsid nohup … > /tmp/x.log 2>&1 < /dev/null &`
  ⇒ ⇒ ⇒ **脱离 harness 进程组** ⇒ ⇒ ⇒ 否则跑到一半就没了（**且退出码是 0** ⇒ ⇒ ⇒
  **极易误判成「跑过了」**）。
- ⚠️ **mock 会话只在内存里** ⇒ ⇒ ⇒ `goto`（整页导航）⇒ **掉登录** ⇒ ⇒ ⇒ 要重登；
  ⇒ ⇒ ⇒ 页面内导航（点菜单）**不掉**。

---

## 教训（**已进 cerebrum / docs/solutions / buglog**，此处只留最新）

- ⚠️ **抓请求体要按 URL 过滤，不是按 body 的内容** ⇒ ⇒ ⇒ body 里**没有**那个串
  ⇒ ⇒ ⇒ 抓到 0 条 ⇒ ⇒ ⇒ 看起来像「前端没发」⇒ ⇒ ⇒ 抓不到**不等于**没发生。
- ⚠️ **落地前先查落点，比先接受推论重要** ⇒ ⇒ ⇒ 「要补就得把模板选择提到建项目之前」
  是**推论** ⇒ ⇒ ⇒ 复核后发现两项**本来就有落点** ⇒ ⇒ ⇒ SPEC / 计划 / STATUS 三处已改。
- ⚠️ **「查不到元素」有三种原因**：元素真没渲染 · **查询方式不对** · **断言恒真**。
- ⚠️ **「走 API 建会先被应用层 409」⇒ 那条 DB 约束的测试是假证据** ⇒ ⇒ 必须**直连 ORM**。
- ⚠️ **契约新增可选字段 ⇒ CI 不红** ⇒ ⇒ ⇒ 手工跑 `npm run api:gen` + **三份都提交**。
- ⚠️ **「已覆盖」要能复核** ⇒ 判据 = **这条断言用的是 `strict_client`**。
- ⚠️ **指标「定义了」≠「有值」** ⇒ 无标签 gauge **创建即报 0** ⇒ 假零比没有更坏。
