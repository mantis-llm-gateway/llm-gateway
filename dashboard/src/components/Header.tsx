export function Header() {
  return (
    <header className="header">
      <div className="header-logo">
        <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
          <path d="M8 1 L13 5 L13 11 L8 15 L3 11 L3 5 Z" />
        </svg>
      </div>
      <span className="header-name">Mantis</span>
      <span className="header-sep" />
      <span className="header-sub">Routing Config</span>
    </header>
  )
}
