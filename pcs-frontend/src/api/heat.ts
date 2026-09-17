/**
 * P5-4 HEAT 计算 + 重量估算 API 客户端（V1.3 SPEC §7.11.6）。
 *
 * 按 SPEC V1.3 §7.11.6 + 后端 OpenAPI（commit 96165e1）：
 * - POST /api/v1/heat/import-htri（multipart/form-data）→ ImportHtriResponse 201
 * - GET /api/v1/heat/{heat_id} → HeatResultResponse 200
 * - POST /api/v1/heat/{heat_id}/weight-estimate → WeightEstimateResponse 200
 *
 * 错误通过 PcsError envelope 抛出（code/message/detail/trace_id）；
 * 401 由 client.ts response interceptor 兜底跳登录，其他 code 由业务层 try/catch。
 *
 * 设计要点：
 * - multipart 上传显式声明 Content-Type=multipart/form-data 让 axios 不强加
 *   boundary（实测 axios 0.27+ 在 FormData + multipart 时无需手动 boundary；保留
 *   声明仅为显式契约）；不显式声明 Content-Type 由浏览器自动加 boundary 更安全。
 * - 此处采用浏览器自动添加方式：传 FormData 时不设 headers（axios 视情况自动
 *   设置 Content-Type 含 boundary；如显式声明则必须手填 boundary 否则 422）。
 * - workspace_id 由调用方传入（项目级 workspace 上下文来自 meta/projects 端点）。
 */

import { api } from './client';
import type {
  ImportHtriResponse,
  HeatResultResponse,
  WeightEstimateRequest,
  WeightEstimateResponse,
} from '../types/heat';

export interface ImportHtriParams {
  file: File;
  project_id: string;
  workspace_id: string;
  equipment_no: string;
  tag_number: string;
  exchanger_category: string;
  equipment_name?: string;
  source_stream_id?: string;
}

export const heatApi = {
  /**POST /api/v1/heat/import-htri（multipart upload）。*/
  importHtri: async (params: ImportHtriParams): Promise<ImportHtriResponse> => {
    const fd = new FormData();
    fd.append('file', params.file);
    fd.append('project_id', params.project_id);
    fd.append('workspace_id', params.workspace_id);
    fd.append('equipment_no', params.equipment_no);
    fd.append('tag_number', params.tag_number);
    fd.append('exchanger_category', params.exchanger_category);
    if (params.equipment_name) fd.append('equipment_name', params.equipment_name);
    if (params.source_stream_id) fd.append('source_stream_id', params.source_stream_id);
    // 不显式声明 Content-Type：让浏览器/axios 自动加 boundary。
    // 显式声明必须手动配 boundary，否则后端 multipart 解析失败（422 HEAT_INPUT_ERROR）。
    const { data } = await api.post<ImportHtriResponse>(
      '/heat/import-htri',
      fd,
    );
    return data;
  },

  /**GET /api/v1/heat/{heat_id}。*/
  get: async (heat_id: string): Promise<HeatResultResponse> => {
    const { data } = await api.get<HeatResultResponse>(`/heat/${heat_id}`);
    return data;
  },

  /**POST /api/v1/heat/{heat_id}/weight-estimate。*/
  estimateWeight: async (
    heat_id: string,
    req: WeightEstimateRequest,
  ): Promise<WeightEstimateResponse> => {
    const { data } = await api.post<WeightEstimateResponse>(
      `/heat/${heat_id}/weight-estimate`,
      req,
    );
    return data;
  },
};