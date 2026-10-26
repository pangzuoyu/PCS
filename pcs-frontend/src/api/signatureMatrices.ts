/**
 * 签署矩阵管理 API 客户端（TODO-070 · P9A-DLV-011 T3 的前端面）。
 *
 * ## 为什么类型**全部**取生成的 OpenAPI 类型
 *
 * 手写 `interface Matrix { ... }` = **第二个真相源** ⇒ 契约改了前端不红 ⇒
 * 上线才炸（本仓已为同类漂移付过代价，见 `src/mocks/handlers.ts` 顶部注释）。
 * ⇒ 一律 `components['schemas'][...]`。
 *
 * ## 权限分层（后端裁决，前端只负责**不误导**）
 *
 * | 动作 | 谁能做 |
 * |---|---|
 * | 建/改矩阵**模板** | SYSTEM_ADMIN（全局表） |
 * | 绑定/解绑**项目** | 全局角色 + 项目授权 + **项目内是项目负责人** |
 *
 * ⚠️ 后端对「不是负责人」的绑定请求返 **403 `PROJECT_ROLE_FORBIDDEN`**
 * ⇒ 前端**不预判**能不能绑（角色口径在后端）⇒ 但**要把 403 显示出来**
 * （否则用户只看到「失败」）。
 */
import { api } from './client';
import type { components } from '../types/api';

export type SignatureMatrix = components['schemas']['SignatureMatrixResponse'];
export type SignatureMatrixList = components['schemas']['SignatureMatrixListResponse'];
export type MatrixStep = components['schemas']['MatrixStepResponse'];
export type MatrixStepInput = components['schemas']['MatrixStepInput'];
export type MatrixBinding = components['schemas']['MatrixBindingResponse'];
export type MatrixUnbind = components['schemas']['MatrixUnbindResponse'];
export type SignatureMatrixRequest = components['schemas']['SignatureMatrixRequest'];
export type SignatureMatrixUpdate = components['schemas']['SignatureMatrixUpdateRequest'];

/** 矩阵可用的模块（= 后端 `MatrixModule` Literal）。 */
export const MATRIX_MODULES = [
  '*',
  'RECORD',
  'STREAM',
  'EQUIP',
  'CHANGE_NOTICE',
] as const;

/** 矩阵状态（= 后端 `MatrixStatus` Literal）。 */
export const MATRIX_STATUSES = ['DRAFT', 'PENDING', 'ACTIVE', 'OBSOLETE'] as const;

export interface MatrixListParams {
  module?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

export const signatureMatricesApi = {
  /** 列矩阵模板（全局配置 ⇒ 不按项目过滤）。 */
  list: (params?: MatrixListParams): Promise<SignatureMatrixList> =>
    api.get<SignatureMatrixList>('/signature-matrices', { params }).then((r) => r.data),

  get: (matrixId: string): Promise<SignatureMatrix> =>
    api.get<SignatureMatrix>(`/signature-matrices/${matrixId}`).then((r) => r.data),

  create: (body: SignatureMatrixRequest): Promise<SignatureMatrix> =>
    api.post<SignatureMatrix>('/signature-matrices', body).then((r) => r.data),

  update: (
    matrixId: string,
    body: SignatureMatrixUpdate,
  ): Promise<SignatureMatrix> =>
    api
      .put<SignatureMatrix>(`/signature-matrices/${matrixId}`, body)
      .then((r) => r.data),

  /** 把矩阵绑到「项目 × 模块」（换绑 = 改同一行）。 */
  bind: (projectId: string, body: { module: string; matrix_id: string }): Promise<MatrixBinding> =>
    api
      .post<MatrixBinding>(`/projects/${projectId}/signature-matrices`, body)
      .then((r) => r.data),

  /** 解绑（本来就没绑 ⇒ `unbound=false`，**不是** 404）。 */
  unbind: (projectId: string, module: string): Promise<MatrixUnbind> =>
    api
      .delete<MatrixUnbind>(`/projects/${projectId}/signature-matrices/${module}`)
      .then((r) => r.data),
};
