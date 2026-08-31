ADR-0023：EquipmentTypeCode项目级可配置
状态	Accepted
日期	2026-08-29
来源	用户素材：Equipment and Piping Numbering Specification
一、决策
EquipmentTypeCode（设备类型代码）不再是全局固定表，改为项目模板中可配置。

用户素材展示的某设计院设备分类代码：

Code	含义	与WORLEY标准的差异
R	Reactor 反应器	一致
V	Vessel/Tank/Container 容器/储罐	一致
T	Column/Tower 塔	一致
D	Dust collector/Decanter 除尘器/倾析器	WORLEY: D=Drum压力容器
A	Agitator 搅拌器	一致
P	Pump 泵	一致
C	Compressor/Fan/Blower 压缩机/风机	一致
E	Heat Exchanger/Cooler 换热器	一致
F	Filter/Strainer 过滤器	一致
S	Furnace/Incinerator/Stack 炉/焚烧炉/烟囱	WORLEY: S=Separator
M	Motor 电机	一致
X	Others/Conveyor/Hoist 其他	一致
关键差异：

S的语义不同（炉 vs 分离器）

D的语义不同（除尘器 vs 压力容器）

仅12个代码 vs WORLEY约80个代码

此规范无PSV/PVRV/PRD等安全阀专用代码（归入X或其他）

二、设计变更
2.1 equipment_type_codes表调整
原设计（V3.0）	新设计
全局固定表，约80种TypeCode	公司级默认表 + 项目级覆写
无project_id字段	增加project_id（nullable，null=公司级，非null=项目级）
P0预置80种	P0仅预置公司默认，项目模板可自定义
2.2 表结构修改
sql
ALTER TABLE equipment_type_codes
ADD COLUMN project_id UUID NULL REFERENCES projects(project_id);

-- 唯一约束：同一项目内type_code唯一
CREATE UNIQUE INDEX uq_type_code_project 
ON equipment_type_codes(COALESCE(project_id::text, ''), type_code);
2.3 与项目模板的关系
项目模板（project_templates.default_config_json）新增：

json
{
  "equipment_type_codes_config": {
    "use_company_default": true,       // 是否使用公司默认
    "project_overrides": [              // 项目级覆写列表
      {
        "type_code": "S",
        "equipment_description": "Furnace, incinerator, stack",
        "description_cn": "炉、焚烧炉、烟囱",
        "category": "STATIC"
      }
    ]
  }
}
2.4 与编号模板的联动
设备编号（tag_number）的第一段就是TypeCode：

text
T 1 0 01 A
│ │ │ │  │
│ │ │ │  └─ 后缀（备用/并联）
│ │ │ └──── 序号
│ │ └─────── 装置号
│ └───────── 区域/系列号
└─────────── 设备类型代码（=TypeCode）
因此TypeCode直接决定tag_number格式。项目级定义TypeCode与ADR-0008（编号模板可配置）天然协同。

三、对SPEC的影响
SPEC	影响
P0	equipment_type_codes表增加project_id列
P2	项目模板增加equipment_type_codes_config
P7	EQUIP_LIST的type_code引用支持项目级覆写
P8	编号模板生成tag_number时使用项目级TypeCode
四、规则
规则	说明
公司级默认	P0预置WORLEY标准约80种（作为参考默认）
项目级覆写	项目模板可覆写任何TypeCode的含义
项目级新增	项目模板可新增TypeCode（如安全阀专用代码）
冲突处理	项目级覆写优先于公司级
不能删除	已使用的TypeCode不可删除（仅可标记作废）
编号联动	tag_number首段必须使用项目有效TypeCode
PCS-DICT-ALL-003 增补文件
文件标识	PCS-DICT-ALL-003-SUP-001
当前版本	V3.1
增补基准	PCS-DICT-ALL-003 V3.0
变更来源	ADR-0023（EquipmentTypeCode项目级可配置）
1. equipment_type_codes表修改
1.1 修改后完整定义
字段名	类型	必填	说明	变更
type_code	string(5)	✅	PK（复合，含project_id）	不变
project_id	UUID	❌	项目级覆写时填写；null=公司级默认	新增
equipment_description	string(200)	✅	英文描述	不变
description_cn	string(100)	❌	中文描述	不变
category	enum	✅	STATIC/ROTATING/PACKAGE/ELECTRICAL/INSTRUMENT/OTHER	不变
is_process_equipment	bool	✅	是否工艺设备	不变
is_pressure_vessel	bool	✅	是否压力容器	不变
source	string	❌	标准来源	不变
status	enum	✅	ACTIVE/OBSOLETE	不变
唯一约束变化：

sql
-- 旧
UNIQUE(type_code)

-- 新
UNIQUE(COALESCE(project_id::text, ''), type_code)
1.2 查询优先级
text
查询TypeCode时按以下优先级：
1. 项目级覆写（project_id = 当前项目）
2. 公司级默认（project_id IS NULL）
2. 项目模板default_config_json新增
json
{
  "equipment_type_codes_config": {
    "use_company_default": true,
    "project_overrides": [
      {
        "type_code": "S",
        "equipment_description": "Furnace, incinerator, stack",
        "description_cn": "炉、焚烧炉、烟囱",
        "category": "STATIC",
        "is_process_equipment": true,
        "is_pressure_vessel": false
      }
    ],
    "project_additions": []
  }
}
3. 与设备编号（tag_number）的关联
设备编号格式：

text
{TypeCode}{Area}{Unit}{SeqNo}{Suffix}
段	说明	来源
TypeCode	设备类型代码（首段）	项目级equipment_type_codes
Area	区域/系列号	编号模板（ADR-0008）
Unit	装置号	编号模板
SeqNo	序号	编号模板SEQUENCE段
Suffix	后缀（备用/并联）	编号模板
规则：编号模板生成tag_number时，首段必须从项目有效TypeCode中选取。

4. 版本历史
版本	日期	修改内容
V3.0	2026-08-29	初始53表版本
V3.1	2026-08-29	增补ADR-0023：equipment_type_codes增加project_id，支持项目级覆写
增补完成。 EquipmentTypeCode现支持：

层级	说明
公司级默认	P0预置参考标准（WORLEY约80种）
项目级覆写	项目模板可覆写S=Furnace等语义差异
项目级新增	项目模板可新增专用代码
这确保了不同设计院/客户的不同设备编号规范都能被PCS适配。
