import { useState, useCallback, createContext, useContext } from 'react';
import { zh } from './zh';
import { zhTW } from './zh-tw';
import { en } from './en';

const langs: Record<string, typeof zh> = { zh, 'zh-TW': zhTW, en };
export type Lang = 'zh' | 'zh-TW' | 'en';
export type { Translations } from './zh';

function detectLang(): Lang {
  const stored = localStorage.getItem('lang') as Lang;
  if (stored && stored in langs) return stored;
  const browserLang = navigator.language?.toLowerCase() || '';
  if (browserLang.startsWith('zh-tw') || browserLang.startsWith('zh-hant')) return 'zh-TW';
  if (browserLang.startsWith('zh')) return 'zh';
  return 'en';
}

export function useLanguage() {
  const [lang, setLang] = useState<Lang>(detectLang);

  const t = langs[lang];

  const switchLang = useCallback((l: Lang) => {
    setLang(l);
    localStorage.setItem('lang', l);
  }, []);

  return { t, lang, switchLang };
}

// Context-based approach for sharing language state across the app
export const LanguageContext = createContext<ReturnType<typeof useLanguage> | null>(null);

export function useT() {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    // Fallback: return zh translations directly when used outside provider
    return langs['zh'];
  }
  return ctx.t;
}
