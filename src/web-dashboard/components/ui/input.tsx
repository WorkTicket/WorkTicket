import { InputHTMLAttributes, ReactNode } from "react";

interface LabelProps {
  htmlFor?: string;
  children: ReactNode;
  className?: string;
}

export function Label({ htmlFor, children, className = "" }: LabelProps) {
  return (
    <label htmlFor={htmlFor} className={`block text-sm font-medium text-gray-700 mb-1 ${className}`}>
      {children}
    </label>
  );
}

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string;
}

export function Input({ error, className = "", ...props }: InputProps) {
  return (
    <input
      className={`w-full border rounded-lg px-3 py-2 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400 ${
        error ? "border-red-300 bg-red-50" : "border-gray-300"
      } ${className}`}
      {...props}
    />
  );
}

interface FormFieldProps {
  label: string;
  htmlFor: string;
  error?: string;
  children: ReactNode;
  required?: boolean;
}

export function FormField({ label, htmlFor, error, children, required }: FormFieldProps) {
  return (
    <div>
      <Label htmlFor={htmlFor}>
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </Label>
      {children}
      {error && <p className="text-red-500 text-xs mt-1">{error}</p>}
    </div>
  );
}
