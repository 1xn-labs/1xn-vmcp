
import * as React from "react"
import { Check, Search, X, ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"

interface SearchableMultiSelectProps {
  options: string[]
  value?: string[]
  onValueChange?: (value: string[]) => void
  placeholder?: string
  searchPlaceholder?: string
  emptyText?: string
  className?: string
  disabled?: boolean
  showClearButton?: boolean
}

export function SearchableMultiSelect({
  options,
  value = [],
  onValueChange,
  placeholder = "Select options...",
  searchPlaceholder = "Search...",
  emptyText = "No options found.",
  className,
  disabled = false,
  showClearButton = true,
}: SearchableMultiSelectProps) {
  const [open, setOpen] = React.useState(false)
  const [searchValue, setSearchValue] = React.useState("")
  const dropdownRef = React.useRef<HTMLDivElement>(null)

  const filteredOptions = React.useMemo(() => {
    if (!searchValue) return options
    return options.filter((option) =>
      option.toLowerCase().includes(searchValue.toLowerCase())
    )
  }, [options, searchValue])

  const handleSelect = (selectedValue: string) => {
    const newValue = value.includes(selectedValue)
      ? value.filter((item) => item !== selectedValue)
      : [...value, selectedValue]
    onValueChange?.(newValue)
    setSearchValue("")
  }

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation()
    onValueChange?.([])
    setSearchValue("")
  }

  const handleRemoveItem = (itemToRemove: string) => {
    onValueChange?.(value.filter((item) => item !== itemToRemove))
  }

  // Close dropdown when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setOpen(false)
        setSearchValue("")
      }
    }

    document.addEventListener("mousedown", handleClickOutside)
    return () => {
      document.removeEventListener("mousedown", handleClickOutside)
    }
  }, [])

  return (
    <div className="relative" ref={dropdownRef}>
      <Button
        type="button"
        variant="outline"
        role="combobox"
        aria-expanded={open}
        className={cn(
          "w-full justify-between bg-background border-border text-foreground hover:bg-muted min-h-10 h-auto",
          className
        )}
        disabled={disabled}
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-1 min-h-6 flex-1 overflow-hidden">
          {value.length > 0 ? (
            <div className="flex items-center gap-1 overflow-x-auto overflow-y-hidden max-h-16 scrollbar-thin scrollbar-thumb-muted scrollbar-track-transparent">
              {value.map((item) => (
                <Badge
                  key={item}
                  variant="secondary"
                  className="text-[10px] px-1.5 py-0.5 flex items-center gap-1 flex-shrink-0 whitespace-nowrap"
                >
                  <span className="truncate max-w-16">{item}</span>
                  <X
                    className="h-2.5 w-2.5 cursor-pointer hover:opacity-70 flex-shrink-0"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleRemoveItem(item)
                    }}
                  />
                </Badge>
              ))}
            </div>
          ) : (
            <span className="truncate text-muted-foreground text-sm">
              {placeholder}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {showClearButton && value.length > 0 && (
            <X
              className="h-4 w-4 opacity-50 hover:opacity-100 cursor-pointer"
              onClick={handleClear}
            />
          )}
          <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
        </div>
      </Button>

      {open && (
        <div className="absolute z-50 w-full mt-1 bg-popover border border-border rounded-md shadow-md">
          <div className="p-2 border-b border-border">
            <div className="relative">
              <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={searchPlaceholder}
                value={searchValue}
                onChange={(e) => setSearchValue(e.target.value)}
                className="pl-8 h-8 text-sm"
                onClick={(e) => e.stopPropagation()}
              />
            </div>
          </div>
          <div className="max-h-60 overflow-y-auto">
            {filteredOptions.length === 0 ? (
              <div className="py-6 text-center text-sm text-muted-foreground">
                {emptyText}
              </div>
            ) : (
              filteredOptions.map((option) => (
                <div
                  key={option}
                  className="flex items-center px-3 py-2 text-sm cursor-pointer hover:bg-muted"
                  onClick={() => handleSelect(option)}
                >
                  <Check
                    className={cn(
                      "mr-2 h-4 w-4",
                      value.includes(option) ? "opacity-100" : "opacity-0"
                    )}
                  />
                  <span className="truncate">{option}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
