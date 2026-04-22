# TypeScript starter (Node.js 22 LTS + TS 5.x)

## Setup

```
cd starter/ts
npm install
```

## Run

```
npm start              # runs agent.ts via tsx
npm run build          # type-checks and emits to dist/
npm test               # runs the shared evaluator against tests/tickets.json
```

## Contract

Export `solveTicket(ticket)` from `agent.ts`. See AGENTS.md §6.3.
