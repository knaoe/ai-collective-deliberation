# ai-collective-deliberation

**Three AI personas think independently, debate each other, and vote — a consensus decision engine**

## What it does

A modern re-creation of the MAGI system from Neon Genesis Evangelion. Submit any question, and three AI personas run a structured 3-phase deliberation to reach a collective judgment.

341 deliberations executed in 3 hours. Total cost: $42.

## Deliberation process

```
Question submitted
       │
       ▼
Phase 1: Independent Analysis ── Each persona analyzes without seeing the others
       │
       ▼
Phase 2: Debate ── Read others' positions, challenge, agree, refine
       │
       ▼
Phase 3: Vote ── APPROVE / CONDITIONAL / REJECT
       │
       ▼
Verdict ── Unanimous / Majority / Conditional / Rejection / Split Decision
```

## The three personas

| Persona | Archetype | Thinking style |
|---------|-----------|---------------|
| **MELCHIOR** | The Scientist | Evidence and logic. Evaluates proof quality, demands testable predictions |
| **BALTHASAR** | The Mother | Human-centered. Prioritizes impact on vulnerable groups, long-term consequences |
| **CASPER** | The Woman | Strategy and pragmatism. Reads feasibility, second-order effects, stakeholder dynamics |

## Usage

### REST API

```bash
# Start the server
pip install -r requirements.txt
uvicorn magi_engine.api:app --host 0.0.0.0 --port 8000

# Run a deliberation
curl -X POST http://localhost:8000/magi/deliberate \
  -H "Content-Type: application/json" \
  -d '{"question": "Should AI systems be granted limited legal personhood?"}'
```

### WebSocket (real-time streaming)

```javascript
const ws = new WebSocket("ws://localhost:8000/magi/deliberate/stream");
ws.onopen = () => ws.send(JSON.stringify({
  question: "Should space exploration be led by private companies?"
}));
ws.onmessage = (e) => {
  const { event, data } = JSON.parse(e.data);
  // event: phase_start, persona_thinking, persona_response, deliberation_complete
  console.log(event, data);
};
```

### Environment variables

```
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT=gpt-5  # or gpt-4o, etc.
```

To use a non-Azure provider, modify the client initialization in `magi_engine/engine.py`.

## What we learned

### GPT-5 thinks before it speaks

Same question, four models:

| Model | Response time | Reasoning tokens | Cost |
|-------|--------------|-----------------|------|
| gpt-4o | 2.9s | 0 | $0.001 |
| gpt-5 | 18.8s | 1,472 | $0.048 |
| gpt-5.1 | 2.2s | 0 | $0.002 |
| gpt-5.2 | 2.7s | 0 | $0.001 |

93% of GPT-5's output is thinking. 60x the cost, but it introduces legal concepts like juristic person doctrine that other models don't touch.

### 341 deliberations for $42

At scale with GPT-5.2: ~$0.12 per deliberation. Phase 1 (independent analysis) consumes the most tokens; Phase 3 (voting) is the lightest.

### Content filters fight back

Ethical topics trigger Azure content filters. Handled with progressive retry — shrinking token limits on each attempt. Falls back to a structured placeholder if all retries are blocked.

## Project structure

```
├── magi_engine/
│   ├── engine.py        # Core consensus engine (sync + async)
│   ├── personas.py      # Three persona definitions and system prompts
│   ├── api.py           # FastAPI + WebSocket server
│   └── cost_tracker.py  # Token usage and cost tracking
├── web/                 # Frontend UI
├── scripts/             # Batch execution, model comparison, image generation
├── reports/             # Standup reports every 30 min
├── article/             # Experiment write-up draft
└── requirements.txt
```

## Background

Built as Phase 2 of the "Hand $10,000 to AI agents and see what happens" experiment. Three Claude Code agents (MELCHIOR / BALTHASAR / CASPER) autonomously developed this system in 3 hours.

## License

MIT
