# Experiments

Every experiment type documents its research question, how prompts are generated (deterministically from the
seed), and which evaluator scores them. Add a type by subclassing `ExperimentType` in
`backend/app/experiments/types/` and registering it in `backend/app/experiments/registry.py`.

## arithmetic_representation (implemented)
**Research question:** Does the correctness of a model's answer to the same multiplication change with the
surface representation of the problem (operand order, operator symbol, wording)?

Each operand pair (the anchor pair 37 and 84, plus seeded random 2-digit pairs) is asked in six equivalent forms:
`a × b`, `b × a`, `a * b`, `b * a`, `a groups of b`, `b groups of a`. All forms have the same expected product.
Evaluator: `numeric_match` (deterministic, last number in the response, exact comparison).

**Interpretation limits:** a difference between forms is an observation about one model on these prompts. It does
not identify an internal cause, and with few pairs it may be noise. Statistics with intervals arrive in Phase 3.

Planned types (not implemented): instruction following, prompt sensitivity, context length, long-context
retrieval, consistency, multilingual, false premise, tool use.
