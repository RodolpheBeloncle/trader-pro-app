/**
 * Composant Badge reutilisable.
 *
 * Affiche un label colore (statut, tag, etc.)
 */

import React from "react";

export type BadgeVariant =
  | "default"
  | "success"
  | "warning"
  | "danger"
  | "info";
export type BadgeSize = "sm" | "md" | "lg";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: BadgeSize;
  /** Affiche un point colore */
  dot?: boolean;
  children: React.ReactNode;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-gray-100 text-gray-800",
  success: "bg-green-100 text-green-800",
  warning: "bg-yellow-100 text-yellow-800",
  danger: "bg-red-100 text-red-800",
  info: "bg-blue-100 text-blue-800",
};

const dotColors: Record<BadgeVariant, string> = {
  default: "bg-gray-400",
  success: "bg-green-400",
  warning: "bg-yellow-400",
  danger: "bg-red-400",
  info: "bg-blue-400",
};

const sizeClasses: Record<BadgeSize, string> = {
  sm: "text-xs px-2 py-0.5",
  md: "text-sm px-2.5 py-0.5",
  lg: "text-base px-3 py-1",
};

export const Badge: React.FC<BadgeProps> = ({
  variant = "default",
  size = "md",
  dot = false,
  children,
  className = "",
  ...props
}) => {
  const baseClasses =
    "inline-flex items-center font-medium rounded-full whitespace-nowrap";

  return (
    <span
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      {dot && (
        <span
          className={`w-1.5 h-1.5 rounded-full mr-1.5 ${dotColors[variant]}`}
        />
      )}
      {children}
    </span>
  );
};

/**
 * Badge specifique pour les performances.
 */
export interface PerfBadgeProps {
  value: number | null;
  size?: BadgeSize;
}

export const PerfBadge: React.FC<PerfBadgeProps> = ({ value, size = "sm" }) => {
  if (value === null) {
    return <Badge variant="default" size={size}>N/A</Badge>;
  }

  const variant: BadgeVariant = value >= 0 ? "success" : "danger";
  const sign = value >= 0 ? "+" : "";

  return (
    <Badge variant={variant} size={size}>
      {sign}{value.toFixed(2)}%
    </Badge>
  );
};
