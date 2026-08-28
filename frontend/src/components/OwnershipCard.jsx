import {
  UNIT_TYPE_LABELS,
  formatDate,
  formatInr,
  unitHatch,
} from '../theme';
import UlpinDimension from './UlpinDimension';

const HISTORY_LABELS = {
  sale: 'Sale',
  mortgage: 'Mortgage',
  inheritance: 'Inheritance',
};

export default function OwnershipCard({ unit }) {
  return (
    <section className="record-block">
      <div className="unit-record-head">
        <h3>
          {unit.floor_number === 0 ? 'Ground' : `Level ${unit.floor_number}`} · Room{' '}
          {unit.unit_number}
        </h3>
        <span className="unit-record-use">
          <i className={`hatch ${unitHatch(unit.unit_type)}`} />
          {UNIT_TYPE_LABELS[unit.unit_type] ?? unit.unit_type}
        </span>
      </div>

      {/* The whole identifier, floor and room included — the base parcel code
          plus the vertical extension, annotated as one dimension string. */}
      <UlpinDimension ulpin={unit.ulpin_3d} caption="Room identifier" variant="issued" />

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
