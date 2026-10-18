/**
 * REPORT_BUILDER 的 MSW handlers + fixtures（b10–b12 / c6）。
 *
 * ## 为什么必须有这一份（2026-10-13 实测发现）
 *
 * dev 环境的登录走 **MSW 的 `mock-login`**（`handlers.ts` 里有 handler），
 * 它返回的是 `MOCK_TOKEN` 这个**假 token**，不是真 JWT。于是：
 *
 * 1. 页面用 `src/api/reportBuilder.ts` 的**真 client** 请求
 * 2. 请求带着 MSW 的假 token 打到真后端
 * 3. 真后端 401
 * 4. `client.ts` 的 response interceptor 清会话 + 跳 `/login`
 *
 * 症状是**用户看到「点进去就被踢回登录页」**，而后端日志只有一条 401，
 * 没有任何代码错误 —— 很容易被误判成「权限配置错了」。
 *
 * ⚠️ 注意第 3 步：`report-builder/datasources` **也要 mock**。只 mock
 * 定义端点的话，字段树仍会 401，页面照样白屏。
 *
 * 与 `src/mocks/heat.ts` 同一形态：真 client 负责生产，MSW 负责 dev 可用。
 *
 * ## 与后端契约的关系
 *
 * 这份 fixture **不是**契约的副本，是让页面在 dev 里能点的东西。
 * **字段形状**用生成的 OpenAPI 类型标注（2026-10-18，评审 #24 / TODO-041）——
 * 契约变了 `tsc` 立刻红，fixture 想漂都漂不动；但**字段内容**（有哪些数据源、
 * 多少字段）与真后端无关 —— 真要验字段树请用 `pcs-backend` 的字段树一致性测试。
 *
 * ⚠️ 标注之前这里全是裸字面量，docstring 却写着「类型不会漂」——
 * 那句话当时是**愿望不是事实**：joins 用了 `left/right` 形状、数据源缺
 * `model`、file status 多了三个契约里没有的字段，`tsc` 一个都没报。
 */
import { http, HttpResponse } from "msw";

import type { components } from "../types/api";

type DatasourceList = components['schemas']['ReportBuilderDatasourceList'];
type DefinitionOut = components['schemas']['ReportDefinitionOut'];
type ExecuteAccepted = components['schemas']['ReportExecuteAccepted'];
type ExecutionStatus = components['schemas']['ReportExecutionStatus'];
type FileStatus = components['schemas']['ReportFileStatusResponse'];
type StyleSummary = components['schemas']['ReportStyleSummary'];

const DEF_ID = '00000000-0000-0000-0000-0000000000b1';
const FILE_ID = '00000000-0000-0000-0000-0000000000c1';
const TASK_ID = 'mock-task-0001';

/** 两条 mock 字段，覆盖 BASIC 与 DETAIL 两级 ——
 * 目的是让明细级切换在页面上**看得见效果**，不是复刻真实 110 个字段。 */
const HEAT_FIELDS = [
  { name: 'tag_number', label: '位号', type: 'string', is_jsonb_key: false,
    level: null, exchanger_type: null },
  { name: 'equipment_no', label: '设备编号', type: 'string', is_jsonb_key: false,
    level: null, exchanger_type: null },
  { name: 'duty', label: '热负荷', type: 'number', is_jsonb_key: false,
    level: null, exchanger_type: null },
  { name: 'tube_count', label: '管程数', type: 'number', is_jsonb_key: false,
    level: 'DETAIL', exchanger_type: null },
  { name: 'shell_tube_count', label: '管程数（HTRI）', type: 'number',
    is_jsonb_key: false, level: 'DETAIL', exchanger_type: null },
  { name: 'ache_params.fan_count', label: '风机数量', type: 'number',
    is_jsonb_key: true, level: 'DETAIL', exchanger_type: 'AIR_COOLER' },
];

const DATASOURCES: DatasourceList = {
  datasources: [
    {
      key: 'HEAT_RESULTS',
      label: '换热器结果',
      model: 'heat_results',
      fields: HEAT_FIELDS,
    },
    {
      key: 'EQUIP_LIST',
      label: '设备一览',
      model: 'equipment_list',
      fields: [
        { name: 'tag_number', label: '位号', type: 'string', is_jsonb_key: false,
          level: null, exchanger_type: null },
        { name: 'vendor', label: '制造商', type: 'string', is_jsonb_key: false,
          level: null, exchanger_type: null },
      ],
    },
  ],
  joins: [
    // ⚠️ 形状来自 ReportBuilderJoin（a/a_field/b/b_field），
    // 这一对在真白名单里存在（EQUIP_LIST ↔ HEAT_RESULTS，按位号）。
    { a: 'EQUIP_LIST', a_field: 'tag_number',
      b: 'HEAT_RESULTS', b_field: 'tag_number', degrade_warn: null },
  ],
};

/** 两条定义：一条 DRAFT、一条 PUBLISHED ——
 * 覆盖「执行」按钮的可用/禁用两种状态。 */
const DEFINITION_BODY: components['schemas']['ReportDefinitionBody-Output'] = {
  DataSources: [{ source: 'HEAT_RESULTS' }],
  SelectedFields: [
    { source: 'HEAT_RESULTS', field: 'tag_number', alias: '位号',
      order: 0, visible: true },
    { source: 'HEAT_RESULTS', field: 'duty', alias: '热负荷',
      order: 1, visible: true },
  ],
  // ⚠️ 故意给**已发布**那条挂一个 AND 分组：第一批的单条模型打开它
  // 会显示「无过滤」而保存抹掉（TODO-060）。留着这个 fixture 才能在
  // 浏览器里一眼看出「嵌套还在」。
  FilterConditions: [
    {
      operator: 'AND',
      conditions: [
        { operator: 'EQ', source: 'HEAT_RESULTS', field: 'tag_number',
          value: 'E-101' },
        { operator: 'GT', source: 'HEAT_RESULTS', field: 'duty', value: 100 },
      ],
    },
  ],
  SortBy: [],
  MaxRows: 10000,
  OutputFormat: 'pdf',
  detailLevel: 'BASIC',
};

/** DRAFT 那条**故意不带过滤** —— 覆盖「无过滤」这条路径，
 *  而 PUBLISHED 那条带 AND 分组，覆盖嵌套。两个状态都验到。 */
const DRAFT_BODY = { ...DEFINITION_BODY, FilterConditions: [] };

const DRAFT: DefinitionOut = {
  def_id: DEF_ID,
  project_id: null,
  name: '换热器明细表',
  category: '设备类',
  description: '按位号 + 热负荷',
  definition_json: DRAFT_BODY,
  output_format: 'pdf',
  max_rows: 10000,
  version: '0.1.0',
  status: 'DRAFT',
  shared_with: 'CREATOR_ONLY',
  created_by: '00000000-0000-0000-0000-0000000000a1',
  created_at: '2026-10-13T00:00:00Z',
  updated_at: null,
};

const PUBLISHED: DefinitionOut = {
  ...DRAFT,
  definition_json: DEFINITION_BODY,
  def_id: '00000000-0000-0000-0000-0000000000b2',
  name: '设备一览',
  category: '设备类',
  description: '位号 + 制造商',
  status: 'PUBLISHED',
  shared_with: 'ALL_USERS',
  version: '0.2.0',
};

const STYLE_V1: StyleSummary = {
  style_id: '00000000-0000-0000-0000-0000000000d1',
  report_type: 'HEAT_DETAIL',
  project_id: null,
  version: '0.1.0',
  status: 'ACTIVE',
  // ⚠️ 2026-10-18 补齐 8 个缺失字段（标注前 tsc 抓出来的第五处漂移：
  // ReportStyle 长过而 fixture 没跟）。默认值对齐后端 style.py。
  style: {
    page_size: 'A4', orientation: 'landscape',
    margins: { top: 20, bottom: 20, left: 18, right: 18 },
    font_family_cn: 'Noto Sans CJK SC', font_family_en: 'Arial',
    font_size_body: 9, font_size_heading: 13, line_spacing: 1.5,
    header: { left: '', center: '', right: '' },
    footer: { left: '', center: '', right: '' },
    table: { header_bg: '#EEF2F7', header_bold: true, border_width: 0.5,
      border_color: '#9CA3AF', cell_padding: 3, zebra_stripe: false,
      max_cell_chars: 60 },
    assumption_mark: '▲', assumption_color: '#FF8C00',
    qr_position: 'footer', qr_size_mm: 20,
    locked_fields: ['page_size', 'orientation'],
  },
};

/** 第二个版本 —— 覆盖「历史版本可回滚」与「同一作用域只有一行 ACTIVE」。 */
const STYLE_V0: StyleSummary = {
  ...STYLE_V1,
  style_id: '00000000-0000-0000-0000-0000000000d0',
  version: '0.0.9',
  status: 'SUPERSEDED',
  style: { ...STYLE_V1.style, font_size_body: 10 },
};

/** 轮询计数（模块级，供「先 RUNNING 后 FINISHED」用）。
 *
 * ⚠️ dev 模块级可变状态：单元测试里跑多个用例时顺序会影响结果。
 * 所以它**只**用于浏览器 dev 演示，不参与契约测试。
 */
let taskPollCount = 0;
export const resetReportBuilderPollCount = () => { taskPollCount = 0; };

const requireAuth = (request: Request) =>
  request.headers.get('Authorization')?.startsWith('Bearer ') ?? false;

const unauthorized = () =>
  HttpResponse.json({ code: 'MISSING_BEARER' }, { status: 401 });

const EXECUTE_ACCEPTED: ExecuteAccepted = {
  task_id: TASK_ID, def_id: DEF_ID, def_version: '0.1.0', status: 'QUEUED',
};

const FILE_STATUS: FileStatus = {
  report_file_id: FILE_ID, status: 'SUCCEEDED', file_format: 'pdf',
  size_bytes: 12345,
};

export const reportBuilderHandlers = [
  // --- 字段树 ---------------------------------------------------------------
  // ⚠️ 必须 mock：不 mock 的话这一条会打到真后端并 401，
  // 页面的字段树恒为空 —— 而「空字段树」看起来像「这个源没有字段」。
  http.get('/api/v1/report-builder/datasources', ({ request }) =>
    (requireAuth(request) ? HttpResponse.json(DATASOURCES) : unauthorized())),

  // --- 定义 ----------------------------------------------------------------
  // ⚠️ **遵守 status 查询参数**（2026-10-18，配套后端 #27）。
  // 后端此前静默丢弃 status；修复后它真的过滤。若 mock 继续无视该参数，
  // dev 里「执行」页会列出 DRAFT、真后端下不会 —— 又一次漂移，
  // 而且方向与 #24 相反：这次 mock 比后端**宽松**。
  http.get('/api/v1/report-builder/definitions', ({ request }) => {
    if (!requireAuth(request)) return unauthorized();
    const status = new URL(request.url).searchParams.get('status');
    const all = [DRAFT, PUBLISHED];
    const items = status ? all.filter((d) => d.status === status) : all;
    return HttpResponse.json({ items, total: items.length });
  }),

  http.get('/api/v1/report-builder/definitions/:defId', ({ request, params }) =>
    (requireAuth(request)
      ? HttpResponse.json(
        params.defId === PUBLISHED.def_id ? PUBLISHED : DRAFT)
      : unauthorized())),

  http.post('/api/v1/report-builder/definitions', ({ request }) =>
    (requireAuth(request) ? HttpResponse.json(DRAFT, { status: 201 })
      : unauthorized())),

  http.put('/api/v1/report-builder/definitions/:defId', ({ request }) =>
    (requireAuth(request) ? HttpResponse.json({ ...DRAFT, version: '0.1.1' })
      : unauthorized())),

  http.post('/api/v1/report-builder/definitions/:defId/publish',
    ({ request }) => (requireAuth(request)
      ? HttpResponse.json({ ...DRAFT, status: 'PUBLISHED', version: '0.1.1' })
      : unauthorized())),

  // --- 执行 ----------------------------------------------------------------
  http.post('/api/v1/report-builder/definitions/:defId/execute',
    ({ request }) => (requireAuth(request)
      // 202 + task_id，**不含文件** —— 与真后端一致（b7 决策）。
      // 页面若假设这里就有文件，会在真后端上白等一轮。
      ? HttpResponse.json(EXECUTE_ACCEPTED, { status: 202 })
      : unauthorized())),

  // ⚠️ 第一次轮询回 RUNNING（无文件），之后回 FINISHED ——
  // 让「转圈 → 出文件」这条路径在 dev 里真的走一遍。
  // 固定回 FINISHED 会让页面一进去就显示完成，看不到等待态。
  http.get('/api/v1/report-builder/executions/:taskId', ({ request }) => {
    if (!requireAuth(request)) return unauthorized();
    const seen = taskPollCount;
    taskPollCount += 1;
    const body: ExecutionStatus = {
      task_id: TASK_ID, def_id: DEF_ID,
      status: seen < 2 ? 'RUNNING' : 'FINISHED',
      report_file_id: seen < 2 ? null : FILE_ID,
    };
    return HttpResponse.json(body);
  }),

  http.get('/api/v1/report/:reportFileId/status', ({ request }) =>
    (requireAuth(request)
      ? HttpResponse.json(FILE_STATUS)
      : unauthorized())),

  // --- 样式（c6）-----------------------------------------------------------
  http.get('/api/v1/report/styles', ({ request }) =>
    (requireAuth(request)
      ? HttpResponse.json({ items: [STYLE_V1, STYLE_V0], total: 2 })
      : unauthorized())),

  http.get('/api/v1/report/styles/:styleId', ({ request, params }) =>
    (requireAuth(request)
      ? HttpResponse.json(params.styleId === STYLE_V0.style_id ? STYLE_V0 : STYLE_V1)
      : unauthorized())),

  http.post('/api/v1/report/styles', async ({ request }) => {
    if (!requireAuth(request)) return unauthorized();
    const body = (await request.json()) as { report_type?: string };
    return HttpResponse.json({
      ...STYLE_V1,
      report_type: body.report_type ?? STYLE_V1.report_type,
      version: '0.1.1', status: 'ACTIVE',
    }, { status: 201 });
  }),

  http.post('/api/v1/report/styles/:styleId/revise', ({ request }) =>
    (requireAuth(request)
      ? HttpResponse.json({ ...STYLE_V1, style_id: '00000000-0000-0000-0000-0000000000d2',
        version: '0.1.2', status: 'ACTIVE' })
      : unauthorized())),

  http.post('/api/v1/report/styles/:styleId/activate', ({ request, params }) =>
    (requireAuth(request)
      ? HttpResponse.json(params.styleId === STYLE_V0.style_id
        ? { ...STYLE_V0, status: 'ACTIVE' }
        : STYLE_V1)
      : unauthorized())),
];

