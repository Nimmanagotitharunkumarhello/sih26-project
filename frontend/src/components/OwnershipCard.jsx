import {
  UNIT_TYPE_LABELS,
  formatDate,
  formatInr,
  unitHatch,
} from '../theme';

const HISTORY_LABELS = {
  sale: 'Sale',
  mortgage: 'Mortgage',
  inheritance: 'Inheritance',
};

/** The vertical extension drawn as a dimension stack: the base parcel, then
 *  each segment branching downward — the identifier descending through the
 *  building the same way the building descends through its levels. */
function ExtensionStack({ unit }) {
  const base = unit.parent_ulpin_2d;
  const rows = [
    { code: `${String(unit.floor_number).padStart(2, '0')}`, label: unit.floor_number === 0 ? 'Ground level' : `Level ${unit.floor_number}` },
    { code: `${String(unit.unit_number).padStart(2, '0')}`, label: `Room ${unit.unit_number}` },
  ];

  return (
    <div className="extension-stack">
      <div className="extension-base">{base}</div>
      <ul className="extension-rows">
        {rows.map((row, index) => (
          <li key={row.code} style={{ '--i': index }}>
            <span className="extension-branch">{index === rows.length - 1 ? '└─' : '├─'}</span>
            <span className="extension-code">{row.code}</span>
            <span>{row.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function OwnershipCard({ unit }) {
  return (
    <section className="record-block">
      <div className="unit-record-head">
        <h3>Room {unit.unit_number}</h3>
        <span className="unit-record-use">
          <i className={`hatch ${unitHatch(unit.unit_type)}`} />
          {UNIT_TYPE_LABELS[unit.unit_type] ?? unit.unit_type}
        </span>
      </div>

      <ExtensionStack unit={unit} />

      <dl className="record-list">
        <div>
          <dt>Owner</dt>
          <dd>{unit.owner_name}</dd>
        </div>
        <div>
          <dt>Aadhaar ref</dt>
          <dd className="mono">{unit.owner_aadhaar_ref}</dd>
        </div>
        <div>
          <dt>Carpet area</dt>
          <dd className="mono">{unit.area_sqft.toLocaleString('en-IN')} ft²</dd>
        </div>
        <div>
          <dt>Held since</dt>
          <dd className="mono">{formatDate(unit.purchase_date)}</dd>
        </div>
      </dl>

      <p className={`encumbrance${unit.encumbrance_flag ? ' is-flagged' : ''}`}>
        {unit.encumbrance_flag ? (
          <>
            <b>Encumbrance on record.</b> {unit.encumbrance_note}
          </>
        ) : (
          'No encumbrance on record.'
        )}
      </p>

      <h3 className="record-heading" style={{ marginTop: '20px' }}>
        Transaction history
        <span className="record-heading-count">{unit.transactions.length}</span>
      </h3>

      <ol className="history">
        {unit.transactions.map((transaction) => (
          <li key={transaction.transaction_id}>
            <span className={`history-type history-${transaction.transaction_type}`}>
              {HISTORY_LABELS[transaction.transaction_type] ?? transaction.transaction_type}
            </span>
            <span className="history-date">{formatDate(transaction.transaction_date)}</span>
            <span className="history-parties">
              {transaction.from_party ? `${transaction.from_party} → ` : ''}
              {transaction.to_party}
            </span>
            {transaction.amount_inr != null && (
              <span className="history-amount">{formatInr(transaction.amount_inr)}</span>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
