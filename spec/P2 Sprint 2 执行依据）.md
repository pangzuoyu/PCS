P2 Sprint 2 执行依据）
一、来源字段组（4个缺失）
#	V3.3字段名	类型	说明
1	in_package	Boolean	是否成套设备内
2	data_sources	String(200)	数据来源（PREL/ESR/PID Rule）
3	tag_in_3d	Boolean	是否已3D建模
4	tag_in_esr	Boolean	是否在ESR中
二、标识字段组（6个缺失）
#	V3.3字段名	类型	说明
5	equipment_name_cn	String(100)	设备中文名称
6	package_no	String(50)	成套包号（如RE-002）
7	sub_project	String(20)	子项目（ISBL/OSBL）
8	unit_no	String(20)	单元号（如5000）
9	unit_name	String(100)	单元名称
10	equipment_description	String(200)	英文描述（命名修正：当前为description）
三、类型字段组（5个缺失）
#	V3.3字段名	类型	说明
11	equipment_sub_type	String(50)	设备子类型（如Shell&Tube）
12	equipment_category	String(30)	设备大类（静设备/转动/成套等）
13	is_pressure_vessel	Boolean	是否压力容器
14	pressure_vessel_category	String(10)	压力容器类别（Ⅰ/Ⅱ/Ⅲ）
四、采购字段组（12个缺失+1个命名修正）
#	V3.3字段名	类型	说明
15	vendor	String(200)	供应商名称（命名修正：当前为vendor_idFK，需新增string列）
16	alternate_vendor	String(200)	备选供应商
17	order_date	Date	下单日期
18	purchase_order_number	String(100)	采购订单号
19	cost	Numeric(18,2)	成本
20	cost_currency	String(10)	币种
21	cost_source	String(200)	成本来源
22	cost_year	Integer	成本年份
23	gpe_spec_number	String(100)	GPE规格书编号
24	gpe_spec_status	String(20)	GPE规格书状态
25	specification_priority	String(100)	规格书优先级
五、图纸字段组（3个缺失）
#	V3.3字段名	类型	说明
26	approval_drawing_received_date	Date	审批图收到日期
27	approval_drawing_return_date	Date	审批图返回日期
28	certified_drawing_received_date	Date	认证图收到日期
六、交付字段组（5个缺失）
#	V3.3字段名	类型	说明
29	delivery_date	Date	交付日期
30	actual_received_date	Date	实际收到日期
31	forecast_on_site	Date	预计到场日期
32	actual_on_site	Date	实际到场日期
33	storage_location	String(200)	存放位置
七、安装字段组（6个缺失）
#	V3.3字段名	类型	说明
34	installation_contract_number	String(100)	安装合同号
35	installation_notes	String(500)	安装备注
36	installation	String(50)	安装方式（MEI/吊装/现场组装）
37	unloading	String(200)	卸车方式
38	loading_by	String(100)	装车负责人
39	installation_location	String(200)	安装位置（命名修正：当前为install_location）
八、重量字段组（4个缺失）
#	V3.3字段名	类型	说明
40	empty_weight	Float	空重kg
41	full_weight	Float	满重kg
42	weigh_cells	Boolean	称重传感器
43	net_weight	Float	净重kg（命名修正：当前为weight_kg）
九、工程字段组（9个缺失+1个命名修正）
#	V3.3字段名	类型	说明
44	process_engineer	String(100)	工艺工程师
45	detail_engineer	String(100)	详细设计工程师
46	flowsheet_drawing_number	String(100)	流程图号（命名修正：当前为drawing_no）
47	pid_drawing_number	String(100)	P&ID图号
48	pid_status	String(10)	P&ID状态
49	dimensions	String(100)	外形尺寸
50	registration_number	String(100)	压力容器注册号
51	emts_number	String(100)	设备物料跟踪系统号
52	mst_number	String(100)	材料规格跟踪号
53	process_engineering_remarks	String(500)	工艺工程备注（命名修正：当前为engineering_notes）
十、涂装字段组（1个命名修正）
#	V3.3字段名	类型	说明
54	paint	String(100)	涂漆规格（命名修正：当前为paint_spec）
汇总统计
类别	数量
完全缺失字段	35个
命名修正字段	7个（description/install_location/weight_kg/paint_spec/drawing_no/engineering_notes/vendor_id处理）
合计需处理	42项
P2 Sprint 2 Migration文件分配
Migration文件	处理项	数量
p2_sprint2_equipment_naming_fix.py	7个命名修正	7项
p2_sprint2_equipment_procurement_delivery.py	采购12+图纸3+交付5+安装6+重量4	30项
p2_sprint2_equipment_engineering.py	工程9+标识6+类型5+来源4+实际数据2	26项
完整清单已列出。 这是P2 Sprint 2的执行依据，届时逐项落地
