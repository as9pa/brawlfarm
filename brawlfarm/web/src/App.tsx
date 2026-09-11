/**
 * The panel's root component.
 *
 * Task 4 replaces this body with the providers, the routes and the live wiring. Until
 * then it proves the whole toolchain in one render: React 19, the Tailwind v4 token
 * utilities from styles/theme.css, and the self-hosted Archivo face.
 */
export function App() {
  return (
    <div className="min-h-screen bg-ground p-6 font-sans text-text">
      <h1 className="text-[28px] font-semibold tracking-tight">brawlfarm</h1>
      <p className="mt-2 text-[13px] text-muted">The panel is being built.</p>
    </div>
  );
}
