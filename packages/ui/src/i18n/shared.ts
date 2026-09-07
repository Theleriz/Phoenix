/**
 * Only the strings genuinely identical in both apps' `copy` dictionaries
 * today (the language-switcher label and option list). App-specific
 * vocabulary stays in each app -- see `docs/architecture/client-side-sensor-connectivity.md`-style
 * reasoning: don't force a merge where the content isn't actually shared yet.
 */
export type Lang = "ru" | "kz" | "en";

export const LANGUAGE_LABEL: Record<Lang, string> = {
  ru: "Язык",
  kz: "Тіл",
  en: "Language",
};

export const LANGUAGE_OPTIONS: { value: Lang; label: string }[] = [
  { value: "ru", label: "РУ" },
  { value: "kz", label: "ҚЗ" },
  { value: "en", label: "EN" },
];
