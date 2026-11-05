"use client";

import type { Language } from "@/lib/i18n";
import { Icon } from "./icons";

type Translate = (text: string) => string;

export function WorkspaceIdentity({
  name,
  status,
  online,
  t,
  onHome,
  onMenu,
}: {
  name: string;
  status: string;
  online: boolean;
  t: Translate;
  onHome: () => void;
  onMenu: () => void;
}) {
  return (
    <header className="sidebar-identity">
      <a
        className="brand"
        href="/"
        aria-label={name}
        onClick={(event) => {
          event.preventDefault();
          onHome();
        }}
      >
        <span className="brand-mark">
          <Icon name="messages" size={24} filled />
        </span>
        <span className="brand-copy">
          <span className="brand-name">{name}</span>
          <span
            className={online ? "connection" : "connection disconnected"}
            role="status"
          >
            <i aria-hidden="true" />
            <span>{status}</span>
          </span>
        </span>
      </a>
      <button
        className="quiet icon-button workspace-menu-trigger"
        aria-label={t("Open menu")}
        aria-haspopup="dialog"
        aria-controls="workspace-navigation"
        onClick={onMenu}
      >
        <Icon name="menu" size={22} />
      </button>
    </header>
  );
}

export function WorkspacePreferences({
  theme,
  language,
  onTheme,
  onLanguage,
  t,
}: {
  theme: string;
  language: Language;
  onTheme: (theme: string) => void;
  onLanguage: (language: Language) => void;
  t: Translate;
}) {
  return (
    <div
      className="sidebar-preferences"
      aria-label={t("Appearance and language")}
    >
      <div
        className="theme-control"
        role="group"
        aria-label={t("Appearance")}
        data-theme={theme}
      >
        {(["light", "dark"] as const).map((mode) => (
          <button
            key={mode}
            className="quiet theme-option"
            aria-label={t(mode === "light" ? "Light mode" : "Dark mode")}
            aria-pressed={theme === mode}
            onClick={() => onTheme(mode)}
          >
            <span className="theme-glyph" key={theme} aria-hidden="true">
              <Icon name={mode === "light" ? "sun" : "moon"} size={18} />
            </span>
            <span>{t(mode === "light" ? "Light" : "Dark")}</span>
          </button>
        ))}
      </div>
      <button
        className="quiet language-switch"
        title={t("Change language")}
        lang={language === "en" ? "fa" : "en"}
        onClick={() => onLanguage(language === "en" ? "fa" : "en")}
      >
        <Icon name="language" size={18} />
        <span>{language === "en" ? "فارسی" : "English"}</span>
      </button>
    </div>
  );
}
