interface YamlConfigurationEditorProps {
  value: string;
  error: string | null;
  onChange: (value: string) => void;
}

export function YamlConfigurationEditor({ value, error, onChange }: YamlConfigurationEditorProps) {
  return (
    <div className="yaml-editor-wrap">
      <label htmlFor="configuration-yaml">Complete configuration YAML</label>
      <textarea
        id="configuration-yaml"
        className={error ? "yaml-editor invalid" : "yaml-editor"}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        spellCheck={false}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? "yaml-error" : "yaml-help"}
      />
      {error
        ? <p className="config-error" id="yaml-error" role="alert">{error}</p>
        : <p className="config-help" id="yaml-help">Form and YAML edit the same versioned object. Unknown keys are rejected.</p>}
    </div>
  );
}
