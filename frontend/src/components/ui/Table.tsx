/**
 * Composants Table reutilisables.
 *
 * Table, TableHeader, TableBody, TableRow, TableCell
 */

import React from "react";

// =============================================================================
// TABLE
// =============================================================================

export interface TableProps extends React.TableHTMLAttributes<HTMLTableElement> {
  children: React.ReactNode;
}

export const Table: React.FC<TableProps> = ({
  children,
  className = "",
  ...props
}) => {
  return (
    <div className="overflow-x-auto">
      <table
        className={`min-w-full divide-y divide-gray-200 ${className}`}
        {...props}
      >
        {children}
      </table>
    </div>
  );
};

// =============================================================================
// TABLE HEADER
// =============================================================================

export interface TableHeaderProps
  extends React.HTMLAttributes<HTMLTableSectionElement> {
  children: React.ReactNode;
}

export const TableHeader: React.FC<TableHeaderProps> = ({
  children,
  className = "",
  ...props
}) => {
  return (
    <thead className={`bg-gray-50 ${className}`} {...props}>
      {children}
    </thead>
  );
};

// =============================================================================
// TABLE BODY
// =============================================================================

export interface TableBodyProps
  extends React.HTMLAttributes<HTMLTableSectionElement> {
  children: React.ReactNode;
}

export const TableBody: React.FC<TableBodyProps> = ({
  children,
  className = "",
  ...props
}) => {
  return (
    <tbody
      className={`bg-white divide-y divide-gray-200 ${className}`}
      {...props}
    >
      {children}
    </tbody>
  );
};

// =============================================================================
// TABLE ROW
// =============================================================================

export interface TableRowProps
  extends React.HTMLAttributes<HTMLTableRowElement> {
  children: React.ReactNode;
  hoverable?: boolean;
  selected?: boolean;
}

export const TableRow: React.FC<TableRowProps> = ({
  children,
  hoverable = true,
  selected = false,
  className = "",
  ...props
}) => {
  const hoverClasses = hoverable ? "hover:bg-gray-50" : "";
  const selectedClasses = selected ? "bg-blue-50" : "";

  return (
    <tr
      className={`${hoverClasses} ${selectedClasses} ${className}`}
      {...props}
    >
      {children}
    </tr>
  );
};

// =============================================================================
// TABLE HEAD CELL
// =============================================================================

export interface TableHeadCellProps
  extends React.ThHTMLAttributes<HTMLTableCellElement> {
  children: React.ReactNode;
  sortable?: boolean;
  sorted?: "asc" | "desc" | null;
  onSort?: () => void;
}

export const TableHeadCell: React.FC<TableHeadCellProps> = ({
  children,
  sortable = false,
  sorted = null,
  onSort,
  className = "",
  ...props
}) => {
  const baseClasses =
    "px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider";
  const sortableClasses = sortable
    ? "cursor-pointer hover:text-gray-700 select-none"
    : "";

  return (
    <th
      className={`${baseClasses} ${sortableClasses} ${className}`}
      onClick={sortable ? onSort : undefined}
      {...props}
    >
      <div className="flex items-center space-x-1">
        <span>{children}</span>
        {sortable && (
          <span className="text-gray-400">
            {sorted === "asc" && "\u2191"}
            {sorted === "desc" && "\u2193"}
            {!sorted && "\u2195"}
          </span>
        )}
      </div>
    </th>
  );
};

// =============================================================================
// TABLE CELL
// =============================================================================

export interface TableCellProps
  extends React.TdHTMLAttributes<HTMLTableCellElement> {
  children: React.ReactNode;
}

export const TableCell: React.FC<TableCellProps> = ({
  children,
  className = "",
  ...props
}) => {
  return (
    <td
      className={`px-4 py-3 whitespace-nowrap text-sm text-gray-900 ${className}`}
      {...props}
    >
      {children}
    </td>
  );
};

// =============================================================================
// TABLE EMPTY STATE
// =============================================================================

export interface TableEmptyProps {
  message?: string;
  colSpan: number;
}

export const TableEmpty: React.FC<TableEmptyProps> = ({
  message = "Aucune donnee disponible",
  colSpan,
}) => {
  return (
    <tr>
      <td
        colSpan={colSpan}
        className="px-4 py-12 text-center text-gray-500 text-sm"
      >
        {message}
      </td>
    </tr>
  );
};
