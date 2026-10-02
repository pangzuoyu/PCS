import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// antd Table / Row / Col use matchMedia for responsive breakpoints;
// jsdom lacks it. Provide a minimal stub.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// antd rc-table 调 window.getComputedStyle(elt, pseudoElt) 计算 scrollbar;
// jsdom 抛 Not implemented. Polyfill 返回空对象 + getPropertyValue 兜底.
const _originalGetComputedStyle = window.getComputedStyle;
window.getComputedStyle = vi.fn((elt: Element, pseudoElt?: string | null) => {
  try {
    return _originalGetComputedStyle.call(window, elt, pseudoElt);
  } catch {
    // 兜底: 返回伪 CSSStyleDeclaration (antd 只读 .getPropertyValue + 数值)
    return {
      getPropertyValue: () => '0px',
    } as unknown as CSSStyleDeclaration;
  }
}) as typeof window.getComputedStyle;

afterEach(() => cleanup());