import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <div>
      <h1 className="text-3xl font-semibold">Page not found</h1>
      <p className="mt-2 text-ink-soft">That address does not exist. <Link className="text-lens underline" to="/">Return home</Link>.</p>
    </div>
  );
}
