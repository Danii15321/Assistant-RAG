"use client";

import { type ModelCatalog, type ModelChoice } from "@/lib/models";

export function ModelPicker({ catalog, model, disabled, onChange, error }: {
  catalog: ModelCatalog; model: ModelChoice; disabled: boolean; error: string;
  onChange: (model: ModelChoice) => void;
}) {
  const money = (value: number) => (value / 1000000).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return <div className="model-picker">
    <label><span className="visually-hidden">Modèle de réponse</span><select disabled={disabled} value={model} onChange={event => onChange(event.target.value as ModelChoice)}>
      {catalog.models.map(item => <option key={item.id} value={item.id} disabled={!item.available}>{item.label}{item.reason ? ` · ${item.reason}` : ""}</option>)}
      {!catalog.models.some(item => item.id === model) && <option value={model} disabled>OpenAI indisponible</option>}
    </select></label>
    {model !== "groq" && catalog.remaining_microusd !== undefined && <small title="Marge réservée avant chaque appel, y compris les erreurs. La facture réelle peut être inférieure.">Budget prudent restant : {money(catalog.remaining_microusd)} $ / 1,00 $</small>}
    {error && <small role="status">{error}</small>}
  </div>;
}
