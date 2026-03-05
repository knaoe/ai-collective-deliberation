# MAGI Project Phase 2

## Project Structure
```
magi-project-2/
├── magi_engine/      # MELCHIOR: Core consensus engine
│   ├── personas.py   # 3 MAGI personas
│   ├── engine.py     # Consensus logic
│   ├── api.py        # FastAPI server
│   └── cost_tracker.py
├── web/              # BALTHASAR: Frontend
│   ├── index.html
│   ├── style.css
│   └── app.js
├── scripts/          # CASPER: Utilities
│   ├── cost_monitor.py
│   ├── generate_images.py
│   └── quick_experiment.py
├── article/          # Final article
├── reports/          # PM standup reports
├── output/           # Generated outputs
└── costs/            # Cost tracking data
```

## Azure Config
- Endpoint: Canaveral (eastus2)
- Models: gpt-5, gpt-5.1, gpt-5.2, gpt-image-1.5
- Resource Group: magi-project

## Rules
- Track token usage for every API call
- Save all outputs to output/ directory
- Don't commit .env or API keys
