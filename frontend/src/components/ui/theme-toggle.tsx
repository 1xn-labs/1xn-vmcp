import { Moon, Sun, Monitor, Palette } from 'lucide-react';
import { Button } from './button.tsx';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem, 
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from './dropdown-menu';
import { useTheme } from '../../contexts/theme-context';

const modeConfig = {
  light: { icon: Sun, label: 'Light' },
  dark: { icon: Moon, label: 'Dark' },
  system: { icon: Monitor, label: 'System' },
};

const paletteConfig = {
  orange: { label: 'Orange', color: 'bg-orange-400' },
  purple: { label: 'Egnaro', color: 'bg-purple-400' },
};

export function ThemeToggle() {
  const { theme, setMode, setPalette } = useTheme();
  
  const CurrentIcon = modeConfig[theme.mode].icon;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="h-9 w-9">
          <CurrentIcon className="h-4 w-4" />
          <span className="sr-only">Toggle theme</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>Theme Settings</DropdownMenuLabel>
        <DropdownMenuSeparator />
        
        <DropdownMenuLabel className="text-xs font-medium text-muted-foreground">
          Mode
        </DropdownMenuLabel>
        {Object.entries(modeConfig).map(([mode, config]) => {
          const Icon = config.icon;
          return (
            <DropdownMenuItem
              key={mode}
              onClick={() => setMode(mode as any)}
              className="flex items-center gap-2"
            >
              <Icon className="h-4 w-4" />
              <span>{config.label}</span>
              {theme.mode === mode && (
                <div className="ml-auto h-2 w-2 rounded-full bg-primary" />
              )}
            </DropdownMenuItem>
          );
        })}
        
        <DropdownMenuSeparator />
        
        <DropdownMenuSub>
          <DropdownMenuSubTrigger className="flex items-center gap-2">
            <Palette className="h-4 w-4" />
            <span>Color Palette</span>
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent>
            {Object.entries(paletteConfig).map(([palette, config]) => (
              <DropdownMenuItem
                key={palette}
                onClick={() => setPalette(palette as any)}
                className="flex items-center gap-2"
              >
                <div className={`h-3 w-3 rounded-full ${config.color}`} />
                <span>{config.label}</span>
                {theme.palette === palette && (
                  <div className="ml-auto h-2 w-2 rounded-full bg-primary" />
                )}
              </DropdownMenuItem>
            ))}
          </DropdownMenuSubContent>
        </DropdownMenuSub>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}