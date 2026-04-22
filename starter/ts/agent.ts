// Entry point for the TypeScript starter.
// The evaluator imports solveTicket from this file. Do not rename or remove it.
// Contract: see AGENTS.md §6.3.

export interface Ticket {
  id: string;
  subject: string;
  body: string;
  metadata?: Record<string, unknown>;
}

export interface Resolution {
  answer: string;
  confidence: number;
  citations: string[];
}

export async function solveTicket(ticket: Ticket): Promise<Resolution> {
  return {
    answer: "",
    confidence: 0.0,
    citations: [],
  };
}
