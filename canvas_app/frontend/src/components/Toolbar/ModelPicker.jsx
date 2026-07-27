export default function ModelPicker({ models, activeModel, onSwitch }) {
  return (
    <div className="model-picker">
      <select
        value={activeModel}
        onChange={(e) => onSwitch(e.target.value)}
      >
        {models.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name || m.id}
          </option>
        ))}
      </select>
    </div>
  )
}
