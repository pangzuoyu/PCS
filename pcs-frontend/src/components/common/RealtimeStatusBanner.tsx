/**
 * RealtimeStatusBanner —— 通知实时推送的状态与降级（P9B-1 · SPEC §6.23）。
 *
 * 依据 P9A-NOT-005/006（ADR-0049 §⑤⑥）。
 *
 * ## 三条纪律
 *
 * 1. ⚠️ **降级的是「及时性」，不是「可达性」** ⇒ 降级文案必须说
 *    「**仍可收到通知**」，且**不得**显示「通知已关闭」这类断言。
 * 2. ⚠️ **横幅不阻断**任何操作。
 * 3. ⚠️ `realtime_reason` 走**枚举映射**（`redis_unavailable` /
 *    `redis_timeout` / `pubsub_error`）⇒ 不把原始英文码当用户文案。
 *
 * ⚠️ `realtime` 检测的是 **pub/sub 可达性**，**不是** Redis 整体健康
 * ⇒ 排障时不得把它当「Redis 挂了」的判据；⚠️ **不得**用于 liveness /
 * readiness 判定。
 */
import { Alert } from 'antd';

export type RealtimeStatus = 'ok' | 'degraded';

/** `realtime_reason` 的**枚举**（后端 `/health` 的取值域）⇒ 逐值给中文说法。 */
const REALTIME_REASON_LABEL: Record<string, string> = {
  redis_unavailable: '实时通道暂不可用',
  redis_timeout: '实时通道响应超时',
  pubsub_error: '实时订阅异常',
};

interface Props {
  realtime: RealtimeStatus;
  reason: string | null;
}

export function RealtimeStatusBanner({ realtime, reason }: Props): JSX.Element | null {
  if (realtime !== 'degraded') return null;

  const reasonLabel = reason ? REALTIME_REASON_LABEL[reason] : null;

  return (
    <Alert
      type="warning"
      showIcon
      data-testid="realtime-status-banner"
      message={
        reasonLabel
          ? `${reasonLabel}：通知改为轮询拉取，「仍可收到通知」，只是不再即时`
          : '通知改为轮询拉取，「仍可收到通知」，只是不再即时'
      }
    />
  );
}

export default RealtimeStatusBanner;
