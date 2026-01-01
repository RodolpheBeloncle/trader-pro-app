import StockRow from './StockRow'

export default function StockTable({ stocks, onSelect, onRemove, onTrade, selectedTicker }) {
  if (stocks.length === 0) {
    return null
  }

  return (
    <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-slate-700/50 text-left text-sm text-slate-400">
              <th className="px-4 py-3 w-12"></th>
              <th className="px-4 py-3">Stock</th>
              <th className="px-4 py-3 text-right">Price</th>
              <th className="px-2 py-3 text-center">3M</th>
              <th className="px-2 py-3 text-center">6M</th>
              <th className="px-2 py-3 text-center">1Y</th>
              <th className="px-2 py-3 text-center">3Y</th>
              <th className="px-2 py-3 text-center">5Y</th>
              <th className="px-4 py-3 text-center">Vol.</th>
              <th className="px-4 py-3 text-center">Div.</th>
              {onTrade && <th className="px-2 py-3 text-center">Action</th>}
              <th className="px-4 py-3 w-12"></th>
            </tr>
          </thead>
          <tbody>
            {stocks.map(stock => (
              <StockRow
                key={stock.ticker}
                stock={stock}
                onSelect={onSelect}
                onRemove={onRemove}
                onTrade={onTrade}
                isSelected={stock.ticker === selectedTicker}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
