import { useState } from "react";

import {
  type AlertType,
  type League,
  type LeagueSetting,
  sendAdminTestAlert,
} from "../../../shared/api";
import { PREFERENCE_LABELS, messageFromUnknown } from "../../../shared/lib/dashboard-ui";
import { LeagueTabs } from "./DashboardFilters";

export function AdminTestAlertsPanel({ token, items }: { token: string; items: LeagueSetting[] }) {
  const [selectedLeague, setSelectedLeague] = useState<League>("NBA");
  const [busyAlertType, setBusyAlertType] = useState<AlertType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const enabledLeagues = items.filter((item) => item.is_enabled);
  const activeLeague =
    enabledLeagues.find((item) => item.league === selectedLeague) ?? enabledLeagues[0] ?? null;

  const onSendTest = async (alertType: AlertType) => {
    if (!activeLeague) return;
    setError(null);
    setResult(null);
    setBusyAlertType(alertType);
    try {
      const response = await sendAdminTestAlert(token, {
        league: activeLeague.league,
        alert_type: alertType,
      });
      const statuses = response.deliveries
        .map((delivery) => `${delivery.channel} ${delivery.status}`)
        .join(", ");
      setResult(
        `${PREFERENCE_LABELS[response.alert_type] ?? response.alert_type} test for ${response.league.replace("_", " ")}: ${statuses}.`,
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
        {activeLeague ? (
          <LeagueTabs
            ariaLabel="Test alert league"
            options={enabledLeagues.map((league) => ({
              value: league.league,
              label: league.label,
            }))}
            value={activeLeague.league}
            onChange={setSelectedLeague}
          />
        ) : null}
      </div>
      <div className="admin-tools-body">
        {activeLeague ? (
          <div className="admin-action-list" aria-label="Test alert actions">
            {activeLeague.alert_types.map((alertType) => (
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
          <p className="admin-panel-message">Enable a league to send test alerts.</p>
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
