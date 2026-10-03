import { FlaskConical } from "lucide-react";
import { useHealth } from "../hooks/useHealth";

/** Shown whenever the backend runs in mock mode, so mock output is never mistaken for evidence. */
export function DemoBanner() {
  const { data } = useHealth();
  if (!data?.mock_mode) return null;
  return (
    <div role="status" className="flex items-start gap-2 bg-demo-wash px-4 py-2 text-sm text-demo">
      <FlaskConical className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <p>
        <strong>DEMO / MOCK DATA.</strong> Model outputs in this mode are deterministic placeholders.
        They are not results from a real LLM and are not experimental evidence.
      </p>
    </div>
  );
}
