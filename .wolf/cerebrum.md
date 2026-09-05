# Cerebrum

> OpenWolf's learning memory. Updated automatically as the AI learns from interactions.
> Do not edit manually unless correcting an error.
> Last updated: 2026-08-27

## User Preferences

<!-- How the user likes things done. Code style, tools, patterns, communication. -->

## Key Learnings

- **Project:** PCS

## Do-Not-Repeat

<!-- Mistakes made and corrected. Each entry prevents the same mistake recurring. -->
<!-- Format: [YYYY-MM-DD] Description of what went wrong and what to do instead. -->

## Decision Log

<!-- Significant technical decisions with rationale. Why X was chosen over Y. -->

## User Preferences (2026-08-28 session)

- 回答设计问题时偏好给出完整结构化方案（表格/状态机图/场景走查/数据字典修改），远超问题本身；我的"推荐选项"只作起点，用户常以更深的设计覆盖之。不要把用户的简短确认当作敷衍——那通常就是终稿。
- 全程中文交流；术语中文为主、枚举/代码标识用英文。
- 用户会当场推翻自己几分钟前的决定（如位号释放→位号终身唯一），立即采纳并同步落盘，不要"保守引用旧版本"。

## Key Learnings

- **Project:** PCS（ProcessCalc Suite）。领域模型核心：两层签署（记录 9 态门禁 / 交付物 Rev+签署矩阵）、哈希判实质变更、位号终身唯一。决议存 docs/adr/0001~0014，术语表 CONTEXT.md，增补 spec/两层签署与变更管理增补规格说明书.md（SUP-007）。
- 文档体系惯例：增补文件声明修改、不直接改基线；基线升版是显式请求才做的动作。

## Do-Not-Repeat

- [2026-08-28] 不要把 ADR 编号按用户口头编号写文件——用户口头说 ADR-0011/0014 时实际对应文件 0009/0012。文件序列编号为准，映射差异在回复中一句话说明即可。

## Decision Log

- [2026-08-28] 15 项领域决议见 docs/adr/0001~0014 + SUP-007；grilling 会话逐项确认。

## Do-Not-Repeat（2026-09-04 SDD 会话）

- [2026-09-04] 手写 CREATE TABLE 迁移前必须查 app/models/mixins.py 的 TimestampMixin 实际列集（created_by/created_at/updated_at 三列，created_at 带 timezone+server_default，updated_at nullable）——brief 里的迁移代码当草图，不当真值。
- [2026-09-04] 凡经 get_async_session_factory() 打真库的测试文件，第二个及以后的 async 测试必须带 _reset_async_engine autouse fixture（单例引擎跨 event loop 会炸）。单个真库测试的文件看不出问题。
- [2026-09-04] 外科切割已提交代码（如切 ORM 字段）后必须复跑依赖该代码的测试——R14 切 asset_id 时测试在切割前跑的，切割后 d71fe10 自带测试就是挂的。
- [2026-09-04] 文件级 git add 手术（soft-reset + 选择性重暂存）会系统性制造"提交不自持"：提交代码依赖的基建留在工作树。手术完成后用干净 worktree 检出验证 import + alembic + pytest，是唯一可信证据；工作树全绿不算数。
- [2026-09-04] 派发评审时要附账本（progress.md）路径——裁决写在那儿，评审看不到就会把有裁决的改动当违规报 Important。

## Key Learnings（2026-09-05 会话）

- [2026-09-05] 公司级管道等级数据源 = 用户 NAS 的 Worley BEP Template 4.3 Piping Material Classification Rev 0（.doc）。等级编码：压力字(A=150Lb,G=1500Lb)+序号+材料字(B=20#,E=304SS,F=塑料)。已提取 6 等级种子 app/seeds/pipe_classes_bep_rev0.{json,xlsx}。
- [2026-09-05] .doc 提取流程：文件名含空格&括号时 libreoffice 转换会静默失败——先 cp 成短名再转 docx，然后 unzip + ElementTree 解析 w:tbl；单元格多值用段落聚合（cells 里空段是 Word 纵向合并的延续）。
- [2026-09-05] vendor/（chemicals 1.5.2/fluids 1.3.1/thermo 0.6.1/CoolProp/ht，P0 入库）零接线至今；chemicals 官方定位纯组分库，无馏分表征（RD80 需自写）；Tb+SG→粘度用 chemicals.viscosity.Twu_1985_internal；水蒸气用 chemicals.iapws（无需 CoolProp）。
- [2026-09-05] 工程常数禁止凭记忆写：先查文献（HAL/期刊 PDF 可拿到原式），再用已知纯组分（n-癸烷 Tb 447.3K SG 0.73）数值闭环验证后才入计划。查不到可靠来源就明确排除（Vc/Zc 先例）。
- [2026-09-05] 用户裁决：管道计算选等级按项目绑定，每个项目可自建管道库（source=PROJECT）；等级编码不跨项目归一，class_id 全局唯一 PK。遗留边界：跨项目同码不同值需复合 PK 迁移，P3 复核。
- [2026-09-05] P2-OPEN-001 三源数据：BEP 4.3 Rev0（6, COMPANY_STD）/ Kaimen ABS IFC SPC-0004-C1（54, PROJECT）/ PPG MRQ-0001（11, PROJECT）。NAS 源路径见各 seed JSON meta。
