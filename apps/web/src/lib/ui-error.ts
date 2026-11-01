// Keep protocol errors unchanged for internal recovery decisions; translate only
// at presentation boundaries, where raw JSON is not a useful next step.
export function uiError(error: unknown): string {
  const message =
    error instanceof Error ? error.message : "Operation unavailable";
  if (message.includes("VAULT_CAPACITY_REACHED"))
    return "Local storage is full. Export your history, then clear delivered history before continuing. Pending messages are preserved.";
  if (
    message.includes("Existing-device approval or verified recovery required")
  )
    return "This browser is still waiting for approval. Use an already approved browser to follow the steps below, then check again.";
  return message;
}
