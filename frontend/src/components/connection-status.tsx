"use client";

import { useState, useSyncExternalStore } from "react";

type Status = "idle" | "checking" | "ready" | "unavailable";

const messages: Record<Status, string> = {
  idle: "Vérifiez que l’application et sa base de données communiquent.",
  checking: "Vérification en cours…",
  ready: "Connexion établie. Le socle local est prêt.",
  unavailable: "Connexion indisponible. Vérifiez que les services locaux sont démarrés, puis réessayez.",
};

function subscribeToHydration() {
  return () => {};
}

export function ConnectionStatus() {
  const [status, setStatus] = useState<Status>("idle");
  // Server HTML must not offer a working control before its handler is hydrated.
  const hydrated = useSyncExternalStore(subscribeToHydration, () => true, () => false);

  async function checkConnection() {
    setStatus("checking");
    try {
      const response = await fetch("/api/v1/health", {
        cache: "no-store",
        signal: AbortSignal.timeout(6000),
      });
      const payload: unknown = await response.json();
      const ready = response.ok && typeof payload === "object" && payload !== null &&
        "status" in payload && payload.status === "ok";
      setStatus(ready ? "ready" : "unavailable");
    } catch {
      setStatus("unavailable");
    }
  }

  return (
    <section className="connection" aria-labelledby="connection-title">
      <div>
        <h2 id="connection-title">Environnement local</h2>
        <p className={`connection-message ${status}`} role="status" aria-live="polite">
          {messages[status]}
        </p>
      </div>
      <button type="button" onClick={checkConnection} disabled={!hydrated || status === "checking"}>
        {status === "checking" ? "Vérification…" : "Vérifier la connexion"}
        <span aria-hidden="true"> ↗</span>
      </button>
    </section>
  );
}
