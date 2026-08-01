import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";

interface ConfigurationListEditorProps {
  label: string;
  items: string[];
  addLabel: string;
  onChange: (items: string[]) => void;
}

export function ConfigurationListEditor({ label, items, addLabel, onChange }: ConfigurationListEditorProps) {
  function move(index: number, direction: -1 | 1) {
    const next = [...items];
    const target = index + direction;
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  }

  return (
    <fieldset className="config-list-editor">
      <legend>{label}</legend>
      {items.map((item, index) => (
        <div className="config-list-row" key={index}>
          <span className="config-list-number">{String(index + 1).padStart(2, "0")}</span>
          <input
            aria-label={`${label} ${index + 1}`}
            value={item}
            onChange={(event) => onChange(items.map((value, itemIndex) => itemIndex === index ? event.target.value : value))}
          />
          <div className="config-list-actions">
            <button type="button" aria-label={`Move ${label} ${index + 1} up`} disabled={index === 0} onClick={() => move(index, -1)}><ArrowUp size={14} /></button>
            <button type="button" aria-label={`Move ${label} ${index + 1} down`} disabled={index === items.length - 1} onClick={() => move(index, 1)}><ArrowDown size={14} /></button>
            <button type="button" aria-label={`Delete ${label} ${index + 1}`} onClick={() => onChange(items.filter((_, itemIndex) => itemIndex !== index))}><Trash2 size={14} /></button>
          </div>
        </div>
      ))}
      <button className="config-add-button" type="button" onClick={() => onChange([...items, ""])}><Plus size={14} /> {addLabel}</button>
    </fieldset>
  );
}
