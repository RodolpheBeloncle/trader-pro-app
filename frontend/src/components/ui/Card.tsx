/**
 * Composant Card reutilisable.
 *
 * Conteneur avec ombre et bordure arrondie.
 */

import React from "react";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Ajoute un padding interne */
  padded?: boolean;
  /** Ajoute un effet de survol */
  hoverable?: boolean;
  children: React.ReactNode;
}

export const Card: React.FC<CardProps> = ({
  padded = true,
  hoverable = false,
  children,
  className = "",
  ...props
}) => {
  const baseClasses = "bg-white rounded-lg shadow-md border border-gray-200";
  const paddingClasses = padded ? "p-4" : "";
  const hoverClasses = hoverable
    ? "transition-shadow hover:shadow-lg cursor-pointer"
    : "";

  return (
    <div
      className={`${baseClasses} ${paddingClasses} ${hoverClasses} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};

export interface CardHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}

export const CardHeader: React.FC<CardHeaderProps> = ({
  title,
  subtitle,
  action,
  className = "",
  ...props
}) => {
  return (
    <div
      className={`flex items-center justify-between mb-4 ${className}`}
      {...props}
    >
      <div>
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        {subtitle && <p className="text-sm text-gray-500">{subtitle}</p>}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
};

export const CardContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  children,
  className = "",
  ...props
}) => {
  return (
    <div className={className} {...props}>
      {children}
    </div>
  );
};

export const CardFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  children,
  className = "",
  ...props
}) => {
  return (
    <div
      className={`mt-4 pt-4 border-t border-gray-200 ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};
