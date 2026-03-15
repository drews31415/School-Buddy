import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import vi    from './locales/vi.json';
import zhCN  from './locales/zh-CN.json';
import zhTW  from './locales/zh-TW.json';
import en    from './locales/en.json';
import ja    from './locales/ja.json';
import th    from './locales/th.json';
import mn    from './locales/mn.json';
import tl    from './locales/tl.json';

i18n
  .use(initReactI18next)
  .init({
    resources: {
      vi:    { translation: vi },
      'zh-CN': { translation: zhCN },
      'zh-TW': { translation: zhTW },
      en:    { translation: en },
      ja:    { translation: ja },
      th:    { translation: th },
      mn:    { translation: mn },
      tl:    { translation: tl },
    },
    lng:           'vi',          // 기본 언어: 베트남어
    fallbackLng:   'en',
    interpolation: { escapeValue: false },
    compatibilityJSON: 'v4',
  });

export default i18n;
