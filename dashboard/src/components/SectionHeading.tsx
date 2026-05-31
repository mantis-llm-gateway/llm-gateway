export function SectionHeading({ title }: { title: string }) {
  return (
    <div className="section-heading">
      <span className="section-dot" />
      <h2>{title}</h2>
    </div>
  )
}
