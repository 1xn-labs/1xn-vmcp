import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

type ThemeMode = 'light' | 'dark' | 'system';
type ColorPalette = 'orange' | 'purple';

interface Theme {
  mode: ThemeMode;
  palette: ColorPalette;
}

interface ThemeContextType {
  theme: Theme;
  isDark: boolean;
  toggleMode: () => void;
  setMode: (mode: ThemeMode) => void;
  setPalette: (palette: ColorPalette) => void;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

interface ThemeProviderProps {
  children: ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const [theme, setTheme] = useState<Theme>({ mode: 'system', palette: 'purple' });
  const [isDark, setIsDark] = useState(false);

  // Initialize theme from localStorage
  useEffect(() => {
    const stored = localStorage.getItem('theme');
    if (stored) {
      try {
        const parsedTheme = JSON.parse(stored) as Theme;
        setTheme(parsedTheme);
      } catch {
        // Fallback for old string-based storage
        const mode = stored as ThemeMode;
        setTheme({ mode: mode || 'system', palette: 'purple' });
      }
    }
  }, []);

  // Handle system theme changes and apply theme
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    
    const updateTheme = () => {
      const root = document.documentElement;
      let shouldBeDark = false;
      
      if (theme.mode === 'system') {
        shouldBeDark = mediaQuery.matches;
      } else {
        shouldBeDark = theme.mode === 'dark';
      }
      
      // Remove all theme classes
      root.classList.remove('dark', 'light');
      root.classList.remove('palette-orange', 'palette-purple');
      
      // Add mode class
      if (shouldBeDark) {
        root.classList.add('dark');
      } else {
        root.classList.add('light');
      }
      
      // Add palette class
      root.classList.add(`palette-${theme.palette}`);
      
      setIsDark(shouldBeDark);
      
      // Store theme preference
      localStorage.setItem('theme', JSON.stringify(theme));
    };

    updateTheme();

    // Listen for system theme changes
    const handleChange = () => {
      if (theme.mode === 'system') {
        updateTheme();
      }
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [theme]);

  const toggleMode = () => {
    const modes: ThemeMode[] = ['light', 'system', 'dark'];
    const currentIndex = modes.indexOf(theme.mode);
    const nextIndex = (currentIndex + 1) % modes.length;
    setTheme({ ...theme, mode: modes[nextIndex] });
  };

  const setMode = (mode: ThemeMode) => {
    setTheme({ ...theme, mode });
  };

  const setPalette = (palette: ColorPalette) => {
    setTheme({ ...theme, palette });
  };

  const contextValue: ThemeContextType = {
    theme,
    isDark,
    toggleMode,
    setMode,
    setPalette,
    setTheme
  };

  return (
    <ThemeContext.Provider value={contextValue}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextType {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}