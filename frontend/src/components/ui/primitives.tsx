"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { clsx } from "clsx";
import { Loader2, X } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from "react";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: Array<string | undefined | false | null>) {
  return twMerge(clsx(inputs));
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", loading = false, disabled, children, ...props }, ref) => {
    const variants: Record<NonNullable<ButtonProps["variant"]>, string> = {
      primary:
        "bg-burnt text-ivory hover:bg-sunset active:translate-y-px border border-sunset/40 shadow-[0_6px_24px_rgba(232,93,25,0.28)]",
      secondary:
        "bg-chocolate text-champagne hover:bg-chocolate/80 border border-champagne/30 active:translate-y-px",
      outline:
        "bg-transparent text-ivory hover:bg-chocolate/45 border border-champagne/35 active:translate-y-px",
      danger:
        "bg-crimson text-ivory hover:bg-crimson/85 border border-red-400/30 active:translate-y-px",
      ghost: "bg-transparent text-champagne hover:bg-chocolate/35 hover:text-ivory",
    };

    const sizes: Record<NonNullable<ButtonProps["size"]>, string> = {
      sm: "min-h-11 px-3.5 py-2 text-xs font-semibold",
      md: "min-h-11 px-5 py-2.5 text-sm font-semibold",
      lg: "min-h-12 px-7 py-3.5 text-sm font-bold tracking-wide",
    };

    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(
          "inline-flex cursor-pointer items-center justify-center gap-2 rounded-md transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-55",
          variants[variant],
          sizes[size],
          className,
        )}
        {...props}
      >
        {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        {children}
      </button>
    );
  },
);
Button.displayName = "Button";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(({ className, error, ...props }, ref) => {
  return (
    <input
      ref={ref}
      aria-invalid={Boolean(error)}
      className={cn(
        "min-h-12 w-full rounded-md border bg-midnight/90 px-4 py-2.5 text-sm text-ivory placeholder:text-ivory-muted/50 transition-colors focus:border-amber focus:outline-none",
        error ? "border-status-err" : "border-champagne/25 hover:border-champagne/45",
        className,
      )}
      {...props}
    />
  );
});
Input.displayName = "Input";

export function StatusBadge({
  tone,
  children,
}: {
  tone: "gold" | "success" | "warning" | "danger" | "neutral";
  children: ReactNode;
}) {
  const tones = {
    gold: "bg-amber/15 text-amber border-amber/40",
    success: "bg-emerald-950/80 text-emerald-300 border-emerald-500/40",
    warning: "bg-amber-950/80 text-amber-200 border-amber-400/40",
    danger: "bg-red-950/80 text-red-200 border-red-500/40",
    neutral: "bg-espresso text-ivory-muted border-champagne/20",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded border px-2.5 py-0.5 text-xs font-semibold",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}

export function ModalDialog({
  open,
  onOpenChange,
  title,
  description,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 max-h-[90dvh] w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-lg border border-champagne/30 bg-espresso p-6 text-ivory shadow-2xl">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="font-display text-2xl tracking-wide text-ivory">
                {title}
              </Dialog.Title>
              {description && (
                <Dialog.Description className="mt-1 text-sm text-ivory-muted">
                  {description}
                </Dialog.Description>
              )}
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close dialog"
                className="inline-flex h-10 w-10 items-center justify-center rounded-md text-champagne hover:bg-chocolate/60"
              >
                <X className="h-5 w-5" />
              </button>
            </Dialog.Close>
          </div>
          <div className="mt-5">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
