// Entry point for the JavaScript starter.
// The evaluator imports solveTicket from this file. Do not rename or remove it.
// Contract: see AGENTS.md §6.2.

export async function solveTicket(ticket) {
  return {
    answer: "",
    confidence: 0.0,
    citations: [],
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const sample = {
    id: "sample-1",
    subject: "Unable to run a test case",
    body: "My submission keeps timing out on the second test case.",
  };
  solveTicket(sample).then((r) => {
    console.log(JSON.stringify(r, null, 2));
  });
}
