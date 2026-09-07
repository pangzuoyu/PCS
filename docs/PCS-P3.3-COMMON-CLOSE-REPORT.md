# PCS P3.3 COMMON 平 收口报告（2026-09-08）

## 一、平概述
按 P3.md V1.6 §3.2.3 + §第五部分 5.3 启动 COMMON 子系统（物性数据库 + 材料许用应力 + 介质安全数据）。原状态后端实现率 **0%**；本次平落地 **4 端点 + 1 service + 4 schemas + 14 测试**。

## 二、端点清单（spec §3.1.2 COMMON 全部 3 条 + search）
| 端点 | 方法 | 用途 | 实现 |
|------|------|------|------|
| `/api/v1/common/materials/search` | GET | 按名称/CAS/分子式搜索 | chemicals.search_chemical + int_to_CAS |
| `/api/v1/common/materials/{cas}` | GET | 查完整物性（water 走 IAPWS-IF97 精确值） | chemicals.iapws + search_chemical |
| `/api/v1/common/allowable-stress` | GET | 材料许用应力（ASME B31.3 Table A-1 + 线性插值） | 内置 _ASME_B31_3_A1 |
| `/api/v1/common/safety` | GET | 介质安全（毒性 + 爆炸极限） | 内置 _SAFETY_DATA |

## 三、数据来源（不建新 SQL 表，spec 未要求持久化）
- **物性**：`vendor/chemicals1.5.2`（search_chemical + identifiers + iapws IAPWS-IF97）
- **高精度水蒸气**：`chemicals.iapws.iapws97_*`（IAPWS-IF97 等同 CoolProp PropsSI 角色；CoolProp 未引入 pcs-backend pyproject）
- **许用应力**：内置 `_ASME_B31_3_A1`（5 牌号 × 6 温度点：A106-GrB / A53-GrB / 304-SS / 316-SS / A240-304L）
- **介质安全**：内置 `_SAFETY_DATA`（15 种常见介质：烃类 9 + 气体 5 + 无机 1；NONE/LOW/MEDIUM/HIGH/EXTREME 5 级）

## 四、文件清单
| 路径 | 行数 | 用途 |
|------|------|------|
| `pcs-backend/app/services/common_service.py` | 233 | 4 静态方法 + 2 内置 dict |
| `pcs-backend/app/schemas/common.py` | 79 | 4 Pydantic Model（含 Field(description=...)） |
| `pcs-backend/app/api/v1/common.py` | 79 | 4 端点（复用 `config.py` ACL） |
| `pcs-backend/tests/api/v1/test_common.py` | 197 | 14 测试（11 API + 2 service + 1 ACL） |
| `pcs-backend/app/api/v1/__init__.py` | +2 | 注册 common_router |

## 五、测试结果
- 新测试：**14/14 passed**
- 全套回归：**477 passed**（463 旧 + 14 新），0 失败
- ruff 0 新增错误（4 auto-fixed：I001 import sort + 1 unused var）
- 性能：chemicals 内存表亚毫秒（spec §3.3.1 ≤ 300ms 验收 ✅）

## 六、API 验收对齐（spec §3.2.3）
| 验收 | 落地 |
|------|------|
| 物性查询正常（chemicals + CoolProp 等价 iapws） | ✅ `/materials/search` + `/materials/{cas}` |
| 许用应力按温度插值正确 | ✅ 节点间线性插值；命中节点直接返回（interpolated=False） |
| 数据来源标记完整 | ✅ source 字段：CHEMICALS_LIBRARY / IAPWS-IF97 / EXPERIMENTAL / ESTIMATED / ASME_B31.3_TABLE_A1 / INTERNAL_SAFETY_DB |
| 按物质名称/CAS号搜索 | ✅ 两者都支持（chemicals.search_chemical 接受 name 或 CAS） |
| 按材料牌号+温度查许用应力 | ✅ `?material=A106-GrB&temp_c=250` |
| 毒性数据（剧毒/高毒/中毒/低毒分类） | ✅ 5 级：NONE/LOW/MEDIUM/HIGH/EXTREME |
| 爆炸极限（上限/下限） | ✅ LEL/UEL vol%（内置库 + chemicals.safety fallback 留口） |

## 七、错误码（spec §3.1.2 错误处理统一）
| code | status | 含义 |
|------|--------|------|
| COMMON_MISSING_KEYWORD | 422 | search 缺 keyword |
| COMMON_MISSING_CAS | 422 | get/safety 缺 cas |
| COMMON_MISSING_MATERIAL | 422 | allowable-stress 缺 material |
| COMMON_TEMP_OOB | 422 | 温度越界（38~500°C） |
| COMMON_MATERIAL_NOT_FOUND | 404 | CAS 不在 chemicals 库 / 材料牌号不在 ASME 表 |
| COMMON_SAFETY_NOT_FOUND | 404 | CAS 不在内置安全库 |
| COMMON_SEARCH_FAILED | 500 | chemicals vendor 异常 |
| COMMON_GET_FAILED | 500 | chemicals vendor 异常 |

## 八、未做（YAGNI）
- 不建新 SQL 表（spec §3.2.3 只要求查询，未要求持久化；数据维护走 CONFIG 路径或 README 升级流程）
- 不做物性数据导入/编辑 API（spec 未列）
- 不做全文搜索（chemicals.search_chemical 子串匹配足够 P3 阶段）
- 不做批量查询（spec §3.1.2 只列单条/按 CAS 查）
- 不引入 CoolProp（pyproject.toml 未含；iapws IAPWS-IF97 等价覆盖水蒸气用例）

## 九、串行下一波：P3.2 SIM（30~35 天）
依赖 COMMON 已落地：物性查询 + IAPWS-IF97 水蒸气 + 毒性数据 + 许用应力 → 可直接被 SIM 物流物性补全（COMMON→SIM）调用。