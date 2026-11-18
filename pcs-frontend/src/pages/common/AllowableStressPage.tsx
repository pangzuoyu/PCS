/**
 * AllowableStressPage — 许用应力（P45-3-3 / Task 30 · **P10-C · T1 改：查询驱动**）。
 *
 * SPEC §7.8.2：
 * - 表格：material / temp_c / stress_mpa / source
 *   （字段名 2026-10-19 对齐契约 `AllowableStressResult`，见 types/common.ts）
 * - 过滤：按 material 模糊查询
 * - 标准来源 Tag
 *
 * ## ⚠️ **P10-C · T1（TODO-160）**：本页改成「**填条件才查**」
 *
 * 契约里 `GET /common/allowable-stress` 的必填参数是 **`material` + `temp_c`**
 * ⇒ ⇒ 此前首屏发**空查询** ⇒ 后端 **422** ⇒ 首屏是错误态。
 * ⇒ ⇒ 现在：**材料牌号与温度都填了才发请求** ⇒ 首屏**零请求**。
 *
 * ## ⚠️ 后端返回的是**单个插值结果**，不是表
 *
 * `CommonService.allowable_stress` 按 (材料, 温度) 查 ASME B31.3 Table A-1
 * ⇒ 返回**一条**（节点间还会插值）⇒ ⇒ 页面把它包成 1 行喂给同一张表
 * ⇒ ⇒ 表格的形状不变，**行数由后端决定**（真实后端 = 1 行）。
 *
 * ⚠️ **SPEC §7.8.2 的「过滤」语义变了**：原来是「按 material 过滤已加载的表」，
 * 现在是「按 material + 温度**查**一条」⇒ ⇒ **登记 SPEC 修订**（见本批说明）。
 */
import { useEffect, useState } from 'react';
import { Alert, Empty, Input, InputNumber, Space, Spin, Table, Tag, Typography } from 'antd';

import { NumericCell } from '../../components/common/NumericCell';
import { commonQueryApi } from '../../api/common';
import { errorText } from '../../api/errors';
import type { AllowableStress } from '../../types/common';
import type { StrictColumns } from '../../types/strictColumns';

/** 输入停止多久才发请求（ms）。 */
const QUERY_DEBOUNCE_MS = 300;

/**
 * `source` 的实际取值形如 `ASME_B31.3_TABLE_A1` / `GB_T_20801…`，
 * 而这张表按**前缀**着色。
 *
 * ⚠️ 2026-10-19 字段从 `standard`（值是 `ASME`/`GB`/`DIN`）改为契约的
 * `source` 之后，若照抄旧键表，`STANDARD_COLOR['ASME_B31.3_TABLE_A1']`
 * 是 undefined ⇒ **每一条标签都变灰**，看起来像「数据有问题」。
 * 改成前缀匹配后观感与之前一致。
 */
const SOURCE_COLOR: { prefix: string; color: string }[] = [
  { prefix: 'ASME', color: 'blue' },
  { prefix: 'GB', color: 'green' },
  { prefix: 'DIN', color: 'orange' },
];

const sourceColor = (src: string): string =>
  SOURCE_COLOR.find((r) => src.startsWith(r.prefix))?.color ?? 'default';

export function AllowableStressPage(): JSX.Element {
  const [material, setMaterial] = useState('');
  const [tempC, setTempC] = useState<number | null>(null);
  const [stresses, setStresses] = useState<AllowableStress[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [queried, setQueried] = useState(false);

  useEffect(() => {
    const mat = material.trim();
    // ⚠️ **两个必填参数缺一不发** ⇒ 首屏（两个都空）**零请求** ⇒ 没有 422。
    if (!mat || tempC === null || Number.isNaN(tempC)) {
      setStresses([]);
      setError(null);
      setQueried(false);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const timer = setTimeout(() => {
      commonQueryApi
        .allowableStress(mat, tempC)
        .then((row) => {
          if (cancelled) return;
          // ⚠️ 后端返回**单个对象** ⇒ 包成 1 行喂给表。
          setStresses([row]);
          setError(null);
          setQueried(true);
          setLoading(false);
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          setStresses([]);
          setError(errorText(err, '许用应力查询失败'));
          setQueried(true);
          setLoading(false);
        });
    }, QUERY_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [material, tempC]);

  const columns: StrictColumns<AllowableStress> = [
    {
      title: '材料',
      dataIndex: 'material',
      width: 120,
      render: (v: string) => (
        <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{v}</span>
      ),
    },
    {
      title: '温度 (°C)',
      dataIndex: 'temp_c',
      width: 100,
      render: (v: number) => <NumericCell value={v} precision={0} precisionType="decimal" unit="°C" />,
    },
    {
      title: '许用应力 (MPa)',
      dataIndex: 'stress_mpa',
      width: 130,
      render: (v: number) => <NumericCell value={v} precision={2} precisionType="decimal" unit="MPa" />,
    },
    {
      title: '数据来源',
      dataIndex: 'source',
      width: 100,
      render: (s: string) => (
        <Tag color={sourceColor(s)} data-testid="stress-standard">
          {s}
        </Tag>
      ),
    },
  ];

  return (
    <div data-testid="allowable-stress-page">
      <Typography.Title level={3}>许用应力</Typography.Title>

      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          data-testid="stress-material-input"
          placeholder="材料牌号（如 A106-B）"
          allowClear
          value={material}
          onChange={(e) => setMaterial(e.target.value)}
          style={{ width: 220 }}
        />
        <InputNumber
          data-testid="stress-temp-input"
          placeholder="温度 °C"
          value={tempC}
          onChange={(v) => setTempC(typeof v === 'number' ? v : null)}
          style={{ width: 140 }}
        />
        <Tag color="blue" data-testid="stress-count">{stresses.length}</Tag>
      </Space>

      {error ? (
        <Alert
          type="error"
          showIcon
          message={error}
          data-testid="stress-error"
          style={{ marginBottom: 16 }}
        />
      ) : null}

      {loading ? (
        <Spin data-testid="stress-loading" />
      ) : stresses.length === 0 ? (
        <Empty
          description={queried ? '无记录' : '输入材料牌号与温度后查询'}
          data-testid="stress-empty"
        />
      ) : (
        <Table<AllowableStress>
          rowKey={(r) => `${r.material}-${r.temp_c}-${r.source}`}
          columns={columns}
          dataSource={stresses}
          pagination={false}
          size="small"
        />
      )}
    </div>
  );
}

export default AllowableStressPage;
