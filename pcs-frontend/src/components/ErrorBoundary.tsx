import { Component, ErrorInfo, ReactNode } from 'react';
import { Button, Result } from 'antd';

/**全局错误边界：捕获子组件树渲染错误，避免整页崩溃白屏。

用法：在 App.tsx 顶层包裹 RouterProvider，rendering 错误统一落到 fallback UI。
- 捕获范围：render / lifecycle / constructor 中的同步 throw
- 不捕获范围：异步事件回调 / setState / SSR / 自身错误
*/
interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // 上报到后端 / Sentry 等；当前 dev 阶段仅 console.error
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  handleReset = (): void => {
    this.setState({ error: null });
    // 重置后回到 dashboard，避免重渲染同一棵坏子树
    window.location.assign('/');
  };

  render(): ReactNode {
    const { error } = this.state;
    if (error) {
      return (
        <Result
          status="500"
          title="页面渲染异常"
          subTitle={error.message || '未知错误'}
          extra={
            <Button type="primary" onClick={this.handleReset}>
              返回首页
            </Button>
          }
        />
      );
    }
    return this.props.children;
  }
}