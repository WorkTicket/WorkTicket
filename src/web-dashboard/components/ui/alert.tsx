import { ReactNode } from "react";

type AlertVariant = "success" | "error" | "warning" | "info";

interface AlertProps {
  variant?: AlertVariant;
  children: ReactNode;
  className?: string;
}

const variantStyles: Record<AlertVariant, string> = {
  success: "bg-green-50 border-green-200 text-green-700",
  warning: "bg-yellow-50 border-yellow-200 text-yellow-700",
  error: "bg-red-50 border-red-200 text-red-700",
  info: "bg-blue-50 border-blue-200 text-blue-700",
};

export function Alert({ variant = "info", children, className = "" }: AlertProps) {
  return (
    <div
      role="alert"
      className={`border rounded-lg p-3 ${variantStyles[variant]} ${className}`}
    >
      {children}
    </div>
  );
}
