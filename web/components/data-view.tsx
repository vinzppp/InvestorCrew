import { Fragment } from "react";

function isPrimitive(value: unknown): value is string | number | boolean | null {
  return value === null || ["string", "number", "boolean"].includes(typeof value);
}

function isPrimitiveArray(value: unknown): value is Array<string | number | boolean | null> {
  return Array.isArray(value) && value.every((item) => isPrimitive(item));
}

export function formatLabel(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function renderPrimitive(value: string | number | boolean | null): string {
  if (value === null) return "n/a";
  return String(value);
}

export function StructuredValue({
  value,
  compact = false
}: {
  value: unknown;
  compact?: boolean;
}) {
  if (isPrimitive(value)) {
    return <span>{renderPrimitive(value)}</span>;
  }

  if (isPrimitiveArray(value)) {
    if (!value.length) {
      return <span className="muted">None</span>;
    }
    return (
      <div className="chip-scroll">
        <div className="chip-row nowrap-row">
          {value.map((item, index) => (
            <span key={`${String(item)}-${index}`} className="metric-chip">
              {renderPrimitive(item)}
            </span>
          ))}
        </div>
      </div>
    );
  }

  if (Array.isArray(value)) {
    if (!value.length) {
      return <span className="muted">None</span>;
    }
    return (
      <div className={compact ? "stack compact-stack" : "stack"}>
        {value.map((item, index) => (
          <details key={index} className="subsection-details">
            <summary>Item {index + 1}</summary>
            <div className="details-body">
              <StructuredValue value={item} compact />
            </div>
          </details>
        ))}
      </div>
    );
  }

  if (typeof value === "object" && value !== null) {
    const entries = Object.entries(value);
    const simple = entries.filter(([, entryValue]) => isPrimitive(entryValue) || isPrimitiveArray(entryValue));
    const complex = entries.filter(([, entryValue]) => !isPrimitive(entryValue) && !isPrimitiveArray(entryValue));

    return (
      <div className={compact ? "stack compact-stack" : "stack"}>
        {simple.length > 0 && (
          <dl className="kv-grid">
            {simple.map(([key, entryValue]) => (
              <Fragment key={key}>
                <div className="kv-item">
                  <dt>{formatLabel(key)}</dt>
                  <dd>
                    {isPrimitiveArray(entryValue) ? (
                      <div className="chip-scroll">
                        <div className="chip-row nowrap-row">
                          {entryValue.map((item, index) => (
                            <span key={`${String(item)}-${index}`} className="metric-chip">
                              {renderPrimitive(item)}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : (
                      renderPrimitive(entryValue)
                    )}
                  </dd>
                </div>
              </Fragment>
            ))}
          </dl>
        )}
        {complex.map(([key, entryValue]) => (
          <details key={key} className="subsection-details">
            <summary>{formatLabel(key)}</summary>
            <div className="details-body">
              <StructuredValue value={entryValue} compact />
            </div>
          </details>
        ))}
      </div>
    );
  }

  return <span>{String(value)}</span>;
}
