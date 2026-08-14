"use client";

import { createContext, use, useEffect, useSyncExternalStore } from "react";

type Locale = "en" | "ko";

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
};

const LocaleContext = createContext<LocaleContextValue>({
  locale: "en",
  setLocale: () => undefined,
});

const STORAGE_KEY = "ai-mot-locale-v1";
const localeListeners = new Set<() => void>();

function subscribeLocale(listener: () => void) {
  localeListeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    localeListeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

function localeSnapshot(): Locale {
  return window.localStorage.getItem(STORAGE_KEY) === "ko" ? "ko" : "en";
}

export function LocalePreferenceProvider({ children }: { children: React.ReactNode }) {
  const locale = useSyncExternalStore(subscribeLocale, localeSnapshot, (): Locale => "en");

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  function updateLocale(nextLocale: Locale) {
    window.localStorage.setItem(STORAGE_KEY, nextLocale);
    localeListeners.forEach((listener) => listener());
  }

  return (
    <LocaleContext value={{ locale, setLocale: updateLocale }}>
      {children}
    </LocaleContext>
  );
}

export function useLocalePreference(): LocaleContextValue {
  return use(LocaleContext);
}

export function LanguageSwitch({ compact = false }: { compact?: boolean }) {
  const { locale, setLocale } = useLocalePreference();
  return (
    <div className={`languageSwitch${compact ? " languageSwitchCompact" : ""}`} aria-label="Display language">
      <button
        aria-pressed={locale === "en"}
        onClick={() => setLocale("en")}
        type="button"
      >
        EN
      </button>
      <button
        aria-pressed={locale === "ko"}
        onClick={() => setLocale("ko")}
        type="button"
      >
        한국어
      </button>
    </div>
  );
}
