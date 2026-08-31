import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { type Competition, updateCompetitionVisibility } from "../../../shared/api";
import { CompetitionMark } from "../../../shared/components/CompetitionMark";
import { SPORT_LABELS, messageFromUnknown } from "../../../shared/lib/dashboard-ui";
import {
  competitionVisibilityQueryOptions,
  competitionsQueryOptions,
  dashboardQueryKeys,
} from "../hooks/dashboard-query-options";

function setsMatch(left: Set<Competition>, right: Set<Competition>) {
  return left.size === right.size && [...left].every((competition) => right.has(competition));
}

export function CompetitionVisibilityModal({
  isOpen,
  token,
  onClose,
}: {
  isOpen: boolean;
  token: string;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const competitionsQuery = useQuery({
    ...competitionsQueryOptions(),
    enabled: isOpen,
  });
  const visibilityQuery = useQuery({
    ...competitionVisibilityQueryOptions(token),
    enabled: isOpen,
  });
  const [draftHidden, setDraftHidden] = useState<Set<Competition>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const competitions = competitionsQuery.data ?? [];
  const visibility = visibilityQuery.data;
  const isReady = competitionsQuery.data !== undefined && visibility !== undefined;
  const queryError = competitionsQuery.error ?? visibilityQuery.error;
  const savedHidden = useMemo(
    () => new Set<Competition>(visibility?.hidden_competitions ?? []),
    [visibility?.hidden_competitions],
  );
  const mutation = useMutation({
    mutationFn: (hiddenCompetitions: Competition[]) =>
      updateCompetitionVisibility(token, hiddenCompetitions),
    onSuccess: (updatedVisibility) => {
      queryClient.setQueryData(dashboardQueryKeys.competitionVisibility(token), updatedVisibility);
      onClose();
    },
    onError: (mutationError) => setError(messageFromUnknown(mutationError)),
  });

  useEffect(() => {
    if (!isOpen || !isReady) return;
    setDraftHidden(new Set(savedHidden));
    setError(null);
  }, [isOpen, isReady, savedHidden]);

  useEffect(() => {
    if (!isOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !mutation.isPending) onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [isOpen, mutation.isPending, onClose]);

  if (!isOpen) return null;

  const toggleCompetition = (competition: Competition) => {
    setDraftHidden((current) => {
      const next = new Set(current);
      if (next.has(competition)) next.delete(competition);
      else next.add(competition);
      return next;
    });
  };
  const showAllActive = () => {
    setDraftHidden((current) => {
      const next = new Set(current);
      competitions.forEach(({ competition }) => next.delete(competition));
      return next;
    });
  };
  const isDirty = isReady && !setsMatch(draftHidden, savedHidden);

  return (
    <div
      className="overlay-sheet"
      role="dialog"
      aria-modal="true"
      aria-labelledby="league-visibility-title"
      aria-describedby="league-visibility-description"
    >
      <section className="overlay-card league-visibility-modal">
        <header className="overlay-card-header">
          <div>
            <h4 id="league-visibility-title">Choose leagues</h4>
            <p id="league-visibility-description" className="muted">
              Select the leagues you want to see in Games and Teams. Your follows and alerts won’t
              change.
            </p>
          </div>
          <button
            className="league-visibility-close"
            type="button"
            aria-label="Close league selector"
            disabled={mutation.isPending}
            onClick={onClose}
          >
            <span aria-hidden>×</span>
          </button>
        </header>

        <div className="league-visibility-body">
          {!isReady && !queryError ? (
            <p className="muted view-feedback league-visibility-loading" role="status">
              Loading leagues...
            </p>
          ) : null}

          {!isReady && queryError ? (
            <div className="view-feedback league-visibility-load-error">
              <p className="error" role="alert">
                {messageFromUnknown(queryError)}
              </p>
              <button
                className="btn btn-secondary"
                type="button"
                onClick={() => {
                  void Promise.all([competitionsQuery.refetch(), visibilityQuery.refetch()]);
                }}
              >
                Retry
              </button>
            </div>
          ) : null}

          {isReady ? (
            <>
              <div className="league-visibility-grid">
                {competitions.map(({ competition, label, sport }) => {
                  const isVisible = !draftHidden.has(competition);
                  return (
                    <label
                      className={`league-visibility-option ${isVisible ? "selected" : ""}`.trim()}
                      key={competition}
                    >
                      <CompetitionMark
                        competition={competition}
                        className="league-visibility-mark"
                        decorative
                      />
                      <span className="league-visibility-copy">
                        <strong>{label}</strong>
                        <span>{SPORT_LABELS[sport]}</span>
                      </span>
                      <input
                        type="checkbox"
                        aria-label={label}
                        checked={isVisible}
                        disabled={mutation.isPending}
                        onChange={() => toggleCompetition(competition)}
                      />
                    </label>
                  );
                })}
              </div>

              {error ? (
                <p className="error league-visibility-save-error" role="alert">
                  {error}
                </p>
              ) : null}
            </>
          ) : null}
        </div>

        {isReady ? (
          <footer className="league-visibility-actions">
            <button
              className="btn btn-secondary"
              type="button"
              disabled={mutation.isPending}
              onClick={showAllActive}
            >
              Select all
            </button>
            <div>
              <button
                className="btn btn-secondary"
                type="button"
                disabled={mutation.isPending}
                onClick={onClose}
              >
                Cancel
              </button>
              <button
                className="btn"
                type="button"
                disabled={!isDirty || mutation.isPending}
                onClick={() => mutation.mutate([...draftHidden])}
              >
                {mutation.isPending ? "Saving…" : "Save changes"}
              </button>
            </div>
          </footer>
        ) : null}
      </section>
    </div>
  );
}
