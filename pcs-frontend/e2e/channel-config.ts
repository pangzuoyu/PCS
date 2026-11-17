/**
 * 真后端通道的**共享常量** —— P10-B 评审 #23。
 *
 * ## 为什么要有这个文件
 *
 * 「真后端通道要连哪个库、哪个项目、哪个端口」这件事**同时**被三处需要：
 *
 * - `playwright.config.ts`（webServer 的 env ⇒ 前端 server 起在哪、代理到哪）
 * - `e2e/global-setup.ts`（fail-fast ⇒ 占位项目 id ⇒ 绿灯是假的）
 * - `e2e/real_backend_flows.spec.ts`（断言用的项目 id）
 *
 * ⇒ 三处各写一份 ⇒ **改一处漏两处** ⇒ 前端查的是另一个项目 ⇒ **空表**
 * ⇒ ⇒ 看着「页面正常」实则没数据 ⇒ **假绿**。
 *
 * ⚠️ **通道常量与生产常量无关** —— `src/constants/env.ts::PROJECT_ID` 是
 * **生产/开发**默认值（占位 id）⇒ 真后端通道**必须**用这里的 flows 项目 id。
 */

/**
 * flows 项目的 id —— `uuid5(NAMESPACE_DNS, "pcs-e2e-flows-project")`。
 *
 * ⚠️ **派生值**（不是随机值）⇒ 跨机器一致 ⇒ 与
 * `pcs-backend/scripts/seed_e2e_flows.py::FLOW_PROJECT_ID` **逐字相同**。
 */
export const FLOW_PROJECT_ID = '2488b011-14fc-584b-966e-1e2dfaeb9eb7';

/**
 * **占位**项目 id —— `src/constants/env.ts` 的默认值。
 *
 * ⚠️ 真后端通道用它 ⇒ 前端查一个**不存在的项目** ⇒ 表格永远没行 ⇒
 * ⇒ **不报错**（axios 只对 401 报错）⇒ ⇒ 绿灯**证明不了**任何事。
 */
export const PLACEHOLDER_PROJECT_ID = '00000000-0000-0000-0000-000000000001';

/** 真后端通道的**前端**端口（5173 是 mock 通道的）。 */
export const REAL_FRONTEND_PORT = 5174;

/**
 * 真后端通道的**后端**默认地址 —— `pcs-backend/scripts/serve_e2e_backend.sh`
 * 起的那个（**不是** `:8000` 的开发后端 ⇒ 免得代理指错 ⇒ 症状是「登录失败」）。
 */
export const DEFAULT_API_PROXY_TARGET = 'http://127.0.0.1:8001';
