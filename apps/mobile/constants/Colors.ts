/**
 * School Buddy 컬러 팔레트 (변경 금지 — CLAUDE.md 규정)
 * 다문화가정 학부모 접근성 기준: 고대비, 직관적 색상 연상
 */
export const Colors = {
  primary:       '#1A5276',  // 진한 파랑 (신뢰, 교육)
  primaryLight:  '#D6EAF8',  // 연한 파랑 (배경)
  accent:        '#E67E22',  // 주황 (중요 알림)
  success:       '#1E8449',  // 초록 (완료, 낮은 중요도)
  warning:       '#E67E22',  // 주황 (중간 중요도)
  danger:        '#C0392B',  // 빨강 (높은 중요도)
  textPrimary:   '#1A1A2E',
  textSecondary: '#5D6D7E',
  background:    '#F8F9FA',
  surface:       '#FFFFFF',
  border:        '#E8ECF0',
  disabled:      '#AEB6BF',
} as const;

export type ColorKey = keyof typeof Colors;
