"use client";

import { ChatIcon } from "@/components/chat-icon";
import { useTheme, type Theme } from "@/components/theme-provider";
const themes: { value: Theme; label: string; icon: "sun" | "moon" | "monitor" }[] = [
  { value: "light", label: "Clair", icon: "sun" },
  { value: "dark", label: "Sombre", icon: "moon" },
  { value: "system", label: "Système", icon: "monitor" },
];
export function SettingsPanel() {
  const { theme, selectTheme } = useTheme();
  return <div className="settings-grid">
    <section className="settings-card"><div className="settings-title"><ChatIcon name="sun" /><h2>Apparence</h2></div>
      <fieldset className="theme-options"><legend>Thème</legend>{themes.map(option => <label key={option.value} className={theme === option.value ? "selected" : ""}>
        <input type="radio" name="theme" value={option.value} checked={theme === option.value} onChange={() => selectTheme(option.value)} /><ChatIcon name={option.icon} /><span>{option.label}</span>
      </label>)}</fieldset><p className="field-help">Le mode système suit votre appareil. Votre choix est mémorisé.</p>
    </section>
    <details className="quiet-details"><summary>Confidentialité et données</summary><p>Vos documents et conversations sont privés. Chaque réponse nécessite votre accord pour envoyer à Groq la question, l’historique utile et les extraits.</p><p>Supprimer un document retire ses extraits des sources. Pour effacer les réponses enregistrées, supprimez aussi la conversation.</p></details>
  </div>;
}
