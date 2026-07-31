export default function ModelPicker({ models, activeModel, onSwitch, loading }) {
  return (
    <div className="model-picker">
      <select
        aria-label="Select model"
        value={activeModel}
        onChange={(e) => onSwitch(e.target.value)}
        disabled={loading}
      >
        {loading && (
          <option value="" disabled>Loading models...</option>
        )}
        {models.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name || m.id}
          </option>
        ))}
      </select>
    </div>
  )
}
