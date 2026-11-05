import { useCallback, useEffect, useState } from 'react';

export type ThemePreference = 'light' | 'dark';
const KEY = 'study-partner.theme.v1';

function initialTheme(): ThemePreference {
  const saved = window.localStorage.getItem(KEY);
  if (saved === 'light' || saved === 'dark') return saved;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light';
}

export function useTheme(): {
  theme: ThemePreference;
  toggleTheme: () => void;
} {
  const [theme, setTheme] = useState<ThemePreference>(initialTheme);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    document.documentElement.style.colorScheme = theme;
    window.localStorage.setItem(KEY, theme);
  }, [theme]);

  const toggleTheme = useCallback(
    () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')),
    []
  );
  return { theme, toggleTheme };
}
