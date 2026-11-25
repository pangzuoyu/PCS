/**
 * 项目 + 我的授权 seed（P10-H · T1 · TODO-194 · 项目选择器的数据源）。
 *
 * ⚠️ **形状照抄契约**（`ProjectOut` / `UserProjectResponse`）⇒ ⇒ 不是随手编的字段
 * ⇒ ⇒ mock 通道与真后端**同一形状**（漂移棘轮盯着）。
 *
 * ⚠️ **两个项目**是故意的 —— 一个项目的话「取第一个」与「能选」**看不出区别**
 * ⇒ ⇒ 棘轮/测试才有意义（真后端通道的种子库里本来就有两个）。
 */
import type { components } from '../../types/api';

type ProjectOut = components['schemas']['ProjectOut'];
type UserProjectResponse = components['schemas']['UserProjectResponse'];

/** mock 通道的默认用户（= `mock-login` 的 `alice`）。 */
export const MOCK_USER_ID = '00000000-0000-0000-0000-0000000a11ce';

export const seedProjects: ProjectOut[] = [
  {
    project_id: '00000000-0000-0000-0000-000000000001',
    project_no: 'PRJ-2026-001',
    project_name: '30 万吨乙烯项目',
    project_type: 'PETROCHEMICAL',
    // ⚠️ `product_category` 有 CHECK 约束（REFINING / ETHYLENE / OTHER）
    product_category: 'ETHYLENE',
    // ⚠️ 派生态：炼油 / 乙烯 ⇒ 等价值；其余 ⇒ 当量值
    electricity_value_type: 'EQUIVALENT_VALUE',
    // ⚠️ 默认**显示**单位制（P10-K · W-2b）—— 存储恒为 canonical(SI)
    unit_system: 'SI',
    // ⚠️ 项目两态（P10-K · W-2c）—— DRAFT = 向导没走完
    status: 'ACTIVE',
  },
  {
    project_id: '00000000-0000-0000-0000-000000000002',
    project_no: 'PRJ-2026-002',
    project_name: '炼油改扩建项目',
    project_type: 'REFINERY',
    product_category: 'REFINING',
    electricity_value_type: 'EQUIVALENT_VALUE',
    unit_system: 'SI',
    status: 'ACTIVE',
  },
];

/**
 * **mock 通道里「已建」的项目**（可变清单）。
 *
 * ⚠️ **为什么需要** —— `POST /api/v1/projects`（`signFlow.ts`）建出来的项目
 * ⇒ ⇒ ⇒ 后续 `GET /api/v1/projects/{id}`（`handlers.ts`）**必须能查到它**
 * ⇒ ⇒ ⇒ ⇒ 否则 dev 里「建完项目 ⇒ 打开它的页」⇒ ⇒ ⇒ **404**
 * ⇒ ⇒ ⇒ ⇒ （而 404 与「项目不存在」同形 ⇒ ⇒ ⇒ ⇒ 用户以为自己没建成）。
 *
 * ⚠️ 这是 **dev 通道的模块级可变状态**（与 `resetReportBuilderPollCount` 同款）
 * ⇒ ⇒ ⇒ **只**用于浏览器演示，不参与契约测试。
 */
export const createdProjects: ProjectOut[] = [];

export const seedUserProjects: UserProjectResponse[] = [
  {
    id: '00000000-0000-0000-0000-00000000a101',
    user_id: MOCK_USER_ID,
    project_id: '00000000-0000-0000-0000-000000000001',
    role_in_project: 'PROJECT_LEAD',
    granted_by: null,
    granted_at: '2026-08-01T09:00:00Z',
    revoked_at: null,
    revoked_by: null,
  },
  {
    id: '00000000-0000-0000-0000-00000000a102',
    user_id: MOCK_USER_ID,
    project_id: '00000000-0000-0000-0000-000000000002',
    role_in_project: 'DESIGNER',
    granted_by: null,
    granted_at: '2026-09-20T09:00:00Z',
    revoked_at: null,
    revoked_by: null,
  },
];
