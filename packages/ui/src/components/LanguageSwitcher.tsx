import { LANGUAGE_LABEL, LANGUAGE_OPTIONS, type Lang } from "../i18n/shared";

export function LanguageSwitcher({ lang, onChange }: { lang: Lang; onChange(lang: Lang): void }) {
  return (
    <label className="language">
      <span>{LANGUAGE_LABEL[lang]}</span>
      <select value={lang} onChange={(e) => onChange(e.target.value as Lang)} aria-label={LANGUAGE_LABEL[lang]}>
        {LANGUAGE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
