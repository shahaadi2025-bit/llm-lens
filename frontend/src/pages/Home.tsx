import { Link } from "react-router-dom";
import { EvidenceLadder } from "../components/EvidenceLadder";

export function Home() {
  return (
    <div className="space-y-12">
      <header className="max-w-2xl">
        <h1 className="text-4xl font-semibold leading-tight text-lens-deep sm:text-5xl">LLM Lens</h1>
        <p className="mt-2 font-display text-xl text-ink-soft">Black-Box LLM Behavioral Intelligence</p>
        <p className="mt-6 leading-relaxed">
          Treat a language model as a black box, change one variable at a time, and record what happens.
          Every number links back to the prompts, responses and evaluators that produced it.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/experiments" className="rounded bg-lens px-4 py-2 text-sm font-medium text-white hover:bg-lens-deep">
            Run experiment
          </Link>
          <Link to="/models" className="rounded border border-rule px-4 py-2 text-sm hover:bg-panel">Explore models</Link>
          <Link to="/experiments" className="rounded border border-rule px-4 py-2 text-sm hover:bg-panel">View experiments</Link>
          <Link to="/dashboard" className="rounded border border-rule px-4 py-2 text-sm hover:bg-panel">Dashboard</Link>
        </div>
      </header>
      <section aria-labelledby="ladder">
        <h2 id="ladder" className="mb-1 text-2xl font-semibold">What a claim has to earn</h2>
        <p className="mb-4 max-w-prose text-sm text-ink-soft">
          Reports never skip a step. A black-box experiment can show that behavior changed; it cannot show why inside the model.
        </p>
        <EvidenceLadder />
      </section>
    </div>
  );
}
