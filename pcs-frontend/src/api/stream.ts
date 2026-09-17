/**streams API 客户端（项目级 SIM 流列表 + 单流详情）。
 *
 * 后端契约：
 * - GET /api/v1/projects/{project_id}/streams → StreamListItem[]
 * - GET /api/v1/streams/{stream_id} → StreamDetail（含矩阵 + 签署 + 审批 + 冲突 + 血缘 + UiSchema）
 *
 * 错误通过 PcsError envelope 抛出；前端 message.error 显示 message 字段。
 *
 * 注意：本文件先放最小 listByProject 方法（HeatComputePage OPEN-6 Select 需要）；
 * get(详情) 等后续 sprint 按需扩展（详情页 UI 在 Sprint 4 stream detail 页面已用内联 mock）。
 */
import { api } from './client';

export interface StreamListItem {
  stream_id: string;
  tag_number: string;
  stream_name: string;
  phase?: string;
  subphase?: string;
}

export const streamApi = {
  /**GET /api/v1/projects/{project_id}/streams。*/
  listByProject: (projectId: string): Promise<StreamListItem[]> =>
    api
      .get<StreamListItem[]>(`/projects/${projectId}/streams`)
      .then((r) => r.data),
};
