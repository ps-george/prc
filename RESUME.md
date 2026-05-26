# Resume — prc

**Status:** Paused 2026-05-26. Not abandoned. Paused because empirical eval showed vanilla LLM beats prc's structured pipeline on raw bug recall, and the pipeline's theoretical value (structured verdict + two-party engagement) needs different evaluation methodology than this v0.1 had.

## What this repo is

A small, local-first PR review tool with a structured verdict + two-party review state machine. Model-agnostic via OpenAI-compatible API. MIT licence. Public at https://github.com/ps-george/prc.

## What got measured

**Bench-B (real-bugs benchmark):** 20 SWE-bench Verified instances, reversed-golden-patch = bug-introducing diff, Sonnet 4.6, $2.55 total.

| System | Recall | False-pos | Cost | Time |
|---|---|---|---|---|
| **vanilla** (single LLM call: "review this PR") | **100%** (20/20) | 65% | $0.20 | 146s |
| prc (structured pipeline) | 90% (18/20) | 60% | $0.51 | 389s |

Vanilla is strictly better on recall, cost, and time. prc's only edge: 5pp lower false-positive rate. Not enough to justify the 2.5× cost premium.

**Bench-A (synthetic injected bugs):** 10/10 recall but the mock LLM is rigged — meaningless. Don't cite this number.

## Why paused

- Vanilla wins on the benchmark prc tries to win on. Honest position.
- The two-party engagement protocol + structured verdict are theoretically the right primitives but they don't show up in "did it catch the bug" eval.
- To validate prc's actual differentiation, need a different evaluation: does the verdict + author-engagement protocol catch hand-wave responses? Does it reduce the "looks-fine, ship it" failure mode? These require human-in-the-loop eval, not LLM-only recall.
- Current attention is on the seed-library-product line; prc waits.

## What to do to resume

If someone wants to push this further, two paths:

### Path A — Validate the differentiation properly (research path)

1. Build an eval where prc's actual edge (structured engagement) could show up:
   - Real PRs (not synthetic) where humans-in-the-loop respond to AI reviews
   - Measure: how often does the AI's review get "looks fine, ship it" responses that turn out to ship bugs?
   - Compare prc's enforced substantive engagement vs vanilla's free-form to see if the protocol reduces those failures
2. This requires human-labeled data and is methodologically subtle. Probably ~2 months of careful work + several thousand dollars in eval costs.

### Path B — Productise the differentiation (product path)

1. Skip the pure benchmark question; design for the human-in-the-loop use case directly
2. Build a GitHub App that posts prc reviews as PR comments + handles the author's responses (accept/refute/clarify) inline
3. Test on real PRs with real authors at small scale
4. Measure outcomes: PR quality before/after, author satisfaction, time-to-merge, bug rate in merged code
5. This is a real product. Cost: ~3-6 months of work + ongoing infra.

### Path C — Don't resume, accept the result

The cleanest path. Repo exists as a reference implementation of a structured review pipeline. The benchmark result is published honestly. Anyone considering building a "structured pipeline" PR review tool can read this repo + the benchmark and learn that structured pipelines underperform single-call LLMs on raw recall at small scale on Sonnet 4.6 — useful negative finding for the community.

## What NOT to do

- Don't tune prc's prompts to win the existing benchmark. That's overfitting.
- Don't claim recall numbers from Bench-A (mock LLM, meaningless).
- Don't oversell the structured-pipeline value without evidence it actually pays off in some setting.

## Where related work lives

- **yaharness** (https://github.com/ps-george/yaharness) is a sibling project — the ReAct agent harness used in the comparison. Also paused.
- **The bilateral-handshake research framework** that motivated the two-party review primitive is in a private repo (`loop-multi-agent`). Empirically negative on bilateral handshake at SWE-bench. None of that work is in prc.
- **Personal seed-library product work** is the current focus and lives in the private seeds repo.
