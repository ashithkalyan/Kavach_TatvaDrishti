import { createContext, useContext, useState, useCallback } from "react";
import { UI, translateValue } from "./translations";

/**
 * Global language state — the fix for "switching language only changed
 * the chat, not the rest of the app". Previously every page held its
 * own local `language` useState with no shared source of truth, so the
 * toggle in the Header only ever affected whichever single page had it
 * wired up. Now every page reads from this one context.
 *
 * Storage: sessionStorage, not localStorage — deliberately mirrors the
 * app's own reasoning for chat-session storage (see CrimeChat.jsx):
 * this is a shared/kiosk-style terminal, so one officer's language
 * choice shouldn't silently carry over into the next officer's login.
 */
const LanguageContext = createContext(null);

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(() => {
    try {
      return sessionStorage.getItem("kavach_language") || "en";
    } catch {
      return "en";
    }
  });

  const setLanguage = useCallback((lang) => {
    setLanguageState(lang);
    try {
      sessionStorage.setItem("kavach_language", lang);
    } catch {
      /* sessionStorage unavailable (e.g. private mode) — language still
         works for this page load, just won't persist across a refresh */
    }
  }, []);

  const toggleLanguage = useCallback(() => {
    setLanguage(language === "en" ? "kn" : "en");
  }, [language, setLanguage]);

  // UI-chrome translation: labels, buttons, headers — instant, no network call
  const t = useCallback((key) => (UI[language] && UI[language][key]) || UI.en[key] || key, [language]);

  // finite-vocabulary value translation: district names, crime-type names
  const tv = useCallback((value) => translateValue(value, language), [language]);

  return (
    <LanguageContext.Provider value={{ language, setLanguage, toggleLanguage, t, tv }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    throw new Error("useLanguage() must be called within a <LanguageProvider>");
  }
  return ctx;
}
