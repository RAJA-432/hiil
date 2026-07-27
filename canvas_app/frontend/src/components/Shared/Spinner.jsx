export default function Spinner({ size = 14 }) {
  return (
    <span
      className="spinner"
      style={{ width: size, height: size }}
      aria-label="Loading"
    />
  )
}
