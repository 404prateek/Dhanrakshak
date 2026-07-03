import { cn } from '../../utils/helpers';

export function Table({ columns, data, className }) {
  return (
    <div className={cn('overflow-x-auto rounded-[18px] border border-[var(--border,#E6EAF0)] bg-white shadow-sm', className)}>
      <table className="min-w-full divide-y divide-[var(--border,#E6EAF0)]">
        <thead className="bg-[var(--bg,#F5F7FA)]">
          <tr>
            {columns.map((col, index) => (
              <th
                key={index}
                scope="col"
                className="sticky top-0 z-10 bg-[var(--bg,#F5F7FA)] px-6 py-4 text-left text-[12px] font-semibold uppercase tracking-[0.14em] text-[var(--secondary-text,#64748B)]"
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border,#E6EAF0)] bg-white">
          {data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-6 py-12 text-center text-sm text-[var(--secondary-text,#64748B)]">
                No data available.
              </td>
            </tr>
          ) : (
            data.map((row, rowIndex) => (
              <tr key={rowIndex} className="hover:bg-blue-50/40 transition-fast">
                {columns.map((col, colIndex) => (
                  <td key={colIndex} className="px-6 py-4 text-sm text-[var(--primary-text,#0F172A)] align-top break-words">
                    {col.cell ? col.cell(row) : row[col.accessorKey]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
