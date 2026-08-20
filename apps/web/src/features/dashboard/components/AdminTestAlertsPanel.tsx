import { useState } from "react";

import {
  type AlertType,
  type Competition,
  type CompetitionSetting,
  sendAdminTestAlert,
} from "../../../shared/api";
import { PREFERENCE_LABELS, messageFromUnknown } from "../../../shared/lib/dashboard-ui";
import { CompetitionTabs } from "./DashboardFilters";

export function AdminTestAlertsPanel({
  token,
  items,
}: {
  token: string;
  items: CompetitionSetting[];
}) {
  const [selectedCompetition, setSelectedCompetition] = useState<Competition>("NBA");
  const [busyAlertType, setBusyAlertType] = useState<AlertType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const enabledCompetitions = items.filter((item) => item.is_enabled);
  const activeCompetition =
    enabledCompetitions.find((item) => item.competition === selectedCompetition) ??
    enabledCompetitions[0] ??
    null;

  const onSendTest = async (alertType: AlertType) => {
    if (!activeCompetition) return;
    setError(null);
    setResult(null);
    setBusyAlertType(alertType);
    try {
      const response = await sendAdminTestAlert(token, {
        competition: activeCompetition.competition,
        alert_type: alertType,
      });
      const statuses = response.deliveries
        .map((delivery) => `${delivery.channel} ${delivery.status}`)
        .join(", ");
      setResult(
        `${PREFERENCE_LABELS[response.alert_type] ?? response.alert_type} test for ${response.competition.replace("_", " ")}: ${statuses}.`,
      );
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusyAlertType(null);
    }
  };

  return (
    <section className="admin-panel surface" aria-labelledby="admin-test-alerts-title">
      <div className="admin-panel-header admin-tools-header surface-header">
        <div>
          <h2 id="admin-test-alerts-title">Test Alerts</h2>
          <p>Send one synthetic alert to validate the delivery flow.</p>
        </div>
        {activeCompetition ? (
          <CompetitionTabs
            ariaLabel="Test alert competition"
            options={enabledCompetitions.map((competition) => ({
              value: competition.competition,
              label: competition.label,
            }))}
            value={activeCompetition.competition}
            onChange={setSelectedCompetition}
          />
        ) : null}
      </div>
      <div className="admin-tools-body">
        {activeCompetition ? (
          <div className="admin-action-list" aria-label="Test alert actions">
            {activeCompetition.alert_types.map((alertType) => (
              <button
                key={alertType}
                className="admin-test-btn"
                type="button"
                disabled={busyAlertType !== null}
                onClick={() => onSendTest(alertType)}
              >
                <span>{PREFERENCE_LABELS[alertType] ?? alertType} test alert</span>
                <span>{busyAlertType === alertType ? "Sending…" : "Send"}</span>
              </button>
            ))}
          </div>
        ) : (
          <p className="admin-panel-message">Enable a competition to send test alerts.</p>
        )}

        {error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : null}
        {result ? (
          <p className="admin-result" role="status" aria-live="polite">
            {result}
          </p>
        ) : null}
      </div>
    </section>
  );
}
