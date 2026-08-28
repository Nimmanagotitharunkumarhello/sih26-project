import { useState } from 'react';
import { splitUlpin } from '../theme';

/** The signature element: a ULPIN annotated the way a measurement is annotated
 *  along a plot edge — digits, a dimension bracket under each segment, then the
 *  segment's name. Grid columns are weighted by character count, which the
 *  monospace face makes align exactly with the characters above.
 *
 *  Renders either width: the 14-character building base, or the full
 *  18-character room identifier, where the vertical extension (floor, room) is
 *  drawn in the accent so the part this project contributes to the scheme reads
 *  apart from the parcel code it extends. */
export default function UlpinDimension({ ulpin, caption, variant = 'paper' }) {
  const [copied, setCopied] = useState(false);
  const segments = splitUlpin(ulpin);
  // Six brackets in one panel width need the abbreviated names and tighter type.
  const compact = segments.length > 4;
  const columns = segments.map((segment) => `${segment.digits}fr`).join(' ');

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(ulpin);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard is blocked over plain http in some browsers. The number is
      // selectable on screen either way, so this needs no error surface.
    }
  };

  const classes = [
    'ulpin-dim',
    compact ? 'is-compact' : '',
    variant === 'issued' ? 'is-issued' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes}>
      <div className="ulpin-dim-caption">
        <span>
          {caption} · {ulpin.length} character
        </span>
        <button type="button" className="ulpin-copy" onClick={copy}>
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>

      <div className="ulpin-grid" style={{ gridTemplateColumns: columns }}>
        {segments.map((segment) => (
          <span
            key={segment.key}
            className={`ulpin-digits${segment.extension ? ' is-extension' : ''}`}
          >
            {segment.value}
          </span>
        ))}
        {segments.map((segment) => (
          <span
            key={`${segment.key}-bracket`}
            className={`ulpin-bracket${segment.extension ? ' is-extension' : ''}`}
          />
        ))}
        {segments.map((segment) => (
          <span
            key={`${segment.key}-label`}
            className={`ulpin-seg-label${segment.extension ? ' is-extension' : ''}`}
          >
            {compact ? segment.short : segment.label}
          </span>
        ))}
      </div>
    </div>
  );
}
