import { theme } from 'antd';

/**
 * PCS AntD 5 主题映射 — 完整 15+ token + components 段
 * UI Spec: docs/PCS-UI-SPEC.md §2 + UI-UX-Pro-Max D-1 Gap 3
 * 所有 token 值走 CSS 变量（pcs-frontend/src/styles/tokens.css），避免色值硬编码
 */
export const antdTheme = {
  algorithm: theme.darkAlgorithm,
  token: {
    /* 背景 */
    colorBgBase: 'var(--bg-canvas)',
    colorBgContainer: 'var(--bg-panel)',
    colorBgElevated: 'var(--bg-elevated)',
    colorBgLayout: 'var(--bg-canvas)',
    /* 边框 */
    colorBorder: 'var(--border-default)',
    colorBorderSecondary: 'var(--border-subtle)',
    /* 主色 */
    colorPrimary: 'var(--accent-primary)',
    colorPrimaryHover: 'var(--accent-hover)',
    colorPrimaryActive: 'var(--accent-active)',
    /* 语义 */
    colorSuccess: 'var(--semantic-success)',
    colorWarning: 'var(--semantic-warning)',
    colorError: 'var(--semantic-danger)',
    colorInfo: 'var(--semantic-info)',
    /* 文字 */
    colorText: 'var(--text-primary)',
    colorTextSecondary: 'var(--text-secondary)',
    colorTextTertiary: 'var(--text-tertiary)',
    colorTextDescription: 'var(--text-secondary)',
    colorTextDisabled: 'var(--text-disabled)',
    /* 字体 */
    fontFamily: 'var(--font-ui)',
    fontFamilyCode: 'var(--font-mono)',
    fontSize: 13,
    /* 形状 */
    borderRadius: 2,
    borderRadiusLG: 4,
    borderRadiusSM: 2,
    /* 控件 */
    controlHeight: 32,
    lineHeight: 1.5,
    /* 禁用态 */
    opacityLoading: 0.7,
    /* 运动 */
    motionDurationFast: '120ms',
    motionDurationMid: '200ms',
    motionDurationSlow: '400ms',
  },
  components: {
    Button: {
      controlHeight: 32,
      borderRadius: 2,
      fontWeight: 500,
    },
    Input: {
      controlHeight: 32,
      paddingBlock: 6,
      colorBgContainer: 'var(--input-bg)',
    },
    InputNumber: {
      controlHeight: 32,
    },
    Select: {
      controlHeight: 32,
      optionSelectedBg: 'var(--accent-subtle)',
    },
    DatePicker: { controlHeight: 32 },
    Table: {
      headerBg: 'var(--table-header-bg)',
      rowHoverBg: 'var(--table-row-hover-bg)',
      borderColor: 'var(--table-border)',
      cellPaddingBlock: 6,
      cellPaddingInline: 12,
    },
    Modal: {
      contentBg: 'var(--bg-panel)',
      headerBg: 'var(--bg-panel)',
    },
    Drawer: {
      colorBgElevated: 'var(--bg-elevated)',
    },
    Menu: {
      itemBg: 'transparent',
      itemSelectedBg: 'var(--accent-subtle)',
      itemSelectedColor: 'var(--accent-primary)',
    },
    Layout: {
      headerBg: 'var(--bg-panel)',
      bodyBg: 'var(--bg-canvas)',
      siderBg: 'var(--bg-panel)',
    },
    Tabs: {
      itemSelectedColor: 'var(--accent-primary)',
      inkBarColor: 'var(--accent-primary)',
    },
  },
};