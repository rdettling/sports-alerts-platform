import { useRef, useState } from "react";

import {
  type AlertType,
  type Competition,
  type CompetitionSetting,
  sendAdminTestAlert,
} from "../../../shared/api";
import { PREFERENCE_LABELS, messageFromUnknown } from "../../../shared/lib/dashboard-ui";

export function AdminTestAlertsPanel({
  token,
  items,
}: {
  token: string;
  items: CompetitionSetting[];
}) {
  const [selectedCompetition, setSelectedCompetition] = useState<Competition | null>(null);
  const [selectedType, setSelectedType] = useState<AlertType | null>(null);
  const [busy, setBusy] = useState(false);
  const sending = useRef(false);
  const [feedback, setFeedback] = useState<{
    competition: Competition;
    alertType: AlertType;
    message: string;
    error: boolean;
  } | null>(null);
  const enabled = items.filter((item) => item.is_enabled);
  const league = enabled.find((item) => item.competition === selectedCompetition) ?? enabled[0];
  const alertType =
    league?.alert_types.find((type) => type === selectedType) ?? league?.alert_types[0];
  const visibleFeedback =
    feedback?.competition === league?.competition && feedback?.alertType === alertType
      ? feedback
      : null;

  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (sending.current || !league || !alertType) return;
    sending.current = true;
    setBusy(true);
    setFeedback(null);
    try {
      const result = await sendAdminTestAlert(token, {
        competition: league.competition,
        alert_type: alertType,
      });
      setFeedback({
        competition: league.competition,
        alertType,
        error: false,
        message: `${PREFERENCE_LABELS[alertType] ?? alertType} test for ${league.label}: ${result.deliveries.map((delivery) => `${delivery.channel} ${delivery.status}`).join(", ")}.`,
      });
    } catch (error) {
      setFeedback({
        competition: league.competition,
        alertType,
        error: true,
        message: messageFromUnknown(error),
      });
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }

  return (
    <section
      className="admin-panel admin-test-panel surface"
      aria-labelledby="admin-test-alerts-title"
    >
      <div className="admin-panel-header surface-header">
        <h2 id="admin-test-alerts-title">Test alerts</h2>
      </div>
      <form className="admin-test-form" onSubmit={send}>
        <fieldset disabled={busy}>
          <label>
            League
            <select
              value={league?.competition ?? ""}
              disabled={!league}
              onChange={(event) => {
                const next = enabled.find((item) => item.competition === event.target.value);
                setSelectedCompetition(next?.competition ?? null);
                setSelectedType(
                  alertType && next?.alert_types.includes(alertType)
                    ? alertType
                    : (next?.alert_types[0] ?? null),
                );
                setFeedback(null);
              }}
            >
              {!league ? <option value="">No enabled leagues</option> : null}
              {enabled.map((item) => (
                <option key={item.competition} value={item.competition}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Alert type
            <select
              value={alertType ?? ""}
              disabled={!alertType}
              onChange={(event) => {
                setSelectedType(event.target.value as AlertType);
                setFeedback(null);
              }}
            >
              {!alertType ? <option value="">No available alert types</option> : null}
              {league?.alert_types.map((type) => (
                <option key={type} value={type}>
                  {PREFERENCE_LABELS[type] ?? type}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={!league || !alertType}>
            {busy ? "Sending…" : "Send test alert"}
          </button>
        </fieldset>
        {!league ? (
          <p>Enable a league in Leagues to send test alerts.</p>
        ) : !alertType ? (
          <p>This league has no supported test alerts.</p>
        ) : null}
        {visibleFeedback ? (
          <p
            className={visibleFeedback.error ? "admin-result is-danger" : "admin-result"}
            role={visibleFeedback.error ? "alert" : "status"}
          >
            {visibleFeedback.message}
          </p>
        ) : null}
      </form>
    </section>
  );
}
