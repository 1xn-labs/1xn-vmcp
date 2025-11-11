
import { useTheme } from "@/contexts/theme-context"
import { Toaster as Sonner, ToasterProps } from "sonner"

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme()

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      richColors={true}
      className="toaster group text-accent border border-border"
      {...props}
    />
  )
}

export { Toaster }
