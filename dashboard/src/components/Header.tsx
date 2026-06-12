import { useState } from "react";
import MantisLockupSvg from "../assets/svgs/MantisLockup";
import SunSvg from "../assets/svgs/Sun";
import MoonSvg from "../assets/svgs/Moon";

export function Header() {
  const [theme, setTheme] = useState<"light" | "dark">(() =>
    document.documentElement.dataset.theme === "dark" ? "dark" : "light",
  );

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    if (next === "dark") {
      document.documentElement.dataset.theme = "dark";
    } else {
      delete document.documentElement.dataset.theme;
    }
    try {
      localStorage.setItem("mantis-theme", next);
    } catch {
      // ignore storage failures (e.g. private browsing)
    }
  }

  return (
    <header className="header">
      <div className="header-brand">
        <MantisLockupSvg />
      </div>

      <button
        type="button"
        className="theme-toggle"
        onClick={toggleTheme}
        aria-label={
          theme === "dark" ? "Switch to light theme" : "Switch to dark theme"
        }
        title={theme === "dark" ? "Light mode" : "Dark mode"}
      >
        {theme === "dark" ? <SunSvg /> : <MoonSvg />}
      </button>
    </header>
  );
}
