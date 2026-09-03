# ADR-0029：折标煤系数组与 DETAIL/HTRI 模板入库

- 状态：起草中（V1.4 P2-OPEN-005 评审）
- 日期：2026-09-04
- 决策者：联合项目组 + 工艺部
- 触发：P2 V1.4 spec 升版 + 偏差审计（commit 35a1614）

## 背景

P2 V1.4 P2-OPEN-005 增补要求：
- CONFIG CATEGORY_3 新增折标煤系数组（toe_conversion_factor / standard_coal_factor）
- CONFIG CATEGORY_4 描述扩展 DETAIL 模板 + HTRI 解析模板
- 模板版本号字段纳入 CONFIG 模板版本序列

须要解决 3 项架构决策。

## 决策

### 决策 1：折标煤系数组归 CATEGORY_3（经验系数管理）
- **理由**：折标煤系数组（toe / standard_coal 系数）属工程经验值，调用方 UTIL 模块按 fuel_type + effective_year 引用
- **替代方案**：归 CATEGORY_5（标准数据库）——否决，因折标煤系数随燃料类型与年份变化频繁，需走 CONFIG 5 态审批而非字典只读

### 决策 2：DETAIL 模板资产归 CATEGORY_4（报表与导入模板管理）
- **理由**：121-A-101.xls / 131-E-102-EOR.xls 是 .xls 模板资产，与现有 Jinja2 / .dotx / .xltx 模板同等地位
- **替代方案**：新建 CATEGORY_7（DETAIL 模板专属）——否决，超出六类框架；DETAIL 仅是 detail_level=DETAIL 的模板实例

### 决策 3：HTRI schema 独立表 htri_template_schemas
- **理由**：列级 schema 需 JSONB 灵活扩展 + 独立版本序列 + 与 TemplateFile 弱耦合
- **替代方案**：塞入 TemplateFile.columns_json JSONB——否决，TemplateFile 主键是模板文件元数据，HTRI schema 主键是列级 schema 元数据，混淆会破坏可追溯性

## 影响

- 新表 2 张：pcs_toe_conversion_factors / htri_template_schemas
- TemplateFile 增字段：template_version_seq
- DICT V3.5 → V3.6 同步
- CATEGORY_3 seed 6 张默认表 + 折标煤系数（基于蜡油加氢—综合能耗.xlsx 实例）

## 后续

- Task 1.10.1 + 1.10.2 + 1.10.3 已执行并提交：7eca3ea（折标煤系数组 + Alembic 迁移 + API）、d71fe10（DETAIL 模板资产入库 + template_version_seq 自动续号）、18e87ef（HTRI schema：ACHE 33 列 + SHELL_TUBE 23 列）
- 本 ADR 与 DICT V3.6 升版 commit 同步推送；评审通过后状态行由「起草中」改「已接受」
