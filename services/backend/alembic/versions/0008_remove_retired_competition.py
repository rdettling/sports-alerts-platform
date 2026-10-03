"""Remove the retired World Cup competition and its derived data.

Revision ID: 0008_remove_retired_competition
Revises: 0007_hockey_overtime_losses
Create Date: 2026-10-02 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0008_remove_retired_competition"
down_revision: Union[str, None] = "0007_hockey_overtime_losses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    op.execute(
        """
        CREATE TEMPORARY TABLE retired_competition_games AS
        SELECT id FROM games WHERE competition = 'WORLD_CUP'
        """
    )
    op.execute(
        """
        CREATE TEMPORARY TABLE retired_competition_teams AS
        SELECT team_id FROM competition_teams WHERE competition = 'WORLD_CUP'
        """
    )
    op.execute(
        """
        DELETE FROM alert_deliveries
        WHERE alert_id IN (
            SELECT id FROM alerts
            WHERE game_id IN (SELECT id FROM retired_competition_games)
        )
        """
    )
    op.execute(
        "DELETE FROM alerts WHERE game_id IN (SELECT id FROM retired_competition_games)"
    )
    op.execute(
        "DELETE FROM user_game_alert_overrides WHERE game_id IN (SELECT id FROM retired_competition_games)"
    )
    op.execute(
        "DELETE FROM user_game_follows WHERE game_id IN (SELECT id FROM retired_competition_games)"
    )
    op.execute(
        "DELETE FROM user_game_unfollows WHERE game_id IN (SELECT id FROM retired_competition_games)"
    )
    op.execute(
        """
        DELETE FROM game_odds_outcomes_current
        WHERE odds_id IN (
            SELECT id FROM game_odds_current
            WHERE game_id IN (SELECT id FROM retired_competition_games)
        )
        """
    )
    op.execute(
        "DELETE FROM game_odds_current WHERE game_id IN (SELECT id FROM retired_competition_games)"
    )
    op.execute("DELETE FROM games WHERE id IN (SELECT id FROM retired_competition_games)")
    op.execute(
        """
        DELETE FROM user_team_follows AS follow
        WHERE follow.team_id IN (SELECT team_id FROM retired_competition_teams)
          AND NOT EXISTS (
              SELECT 1 FROM competition_teams AS membership
              WHERE membership.team_id = follow.team_id
                AND membership.competition <> 'WORLD_CUP'
          )
        """
    )
    op.execute("DELETE FROM competition_teams WHERE competition = 'WORLD_CUP'")
    op.execute(
        """
        DELETE FROM teams AS team
        WHERE team.id IN (SELECT team_id FROM retired_competition_teams)
          AND NOT EXISTS (
              SELECT 1 FROM competition_teams AS membership
              WHERE membership.team_id = team.id
          )
          AND NOT EXISTS (
              SELECT 1 FROM games
              WHERE home_team_id = team.id OR away_team_id = team.id
          )
        """
    )
    op.execute("DELETE FROM competition_settings WHERE competition = 'WORLD_CUP'")
    if dialect == "postgresql":
        op.execute(
            """
            UPDATE users
            SET hidden_competitions = (hidden_competitions::jsonb - 'WORLD_CUP')::json
            WHERE hidden_competitions::jsonb ? 'WORLD_CUP'
            """
        )
    else:
        op.execute(
            """
            UPDATE users
            SET hidden_competitions = COALESCE(
                (
                    SELECT json_group_array(value)
                    FROM json_each(users.hidden_competitions)
                    WHERE value <> 'WORLD_CUP'
                ),
                '[]'
            )
            WHERE EXISTS (
                SELECT 1 FROM json_each(users.hidden_competitions)
                WHERE value = 'WORLD_CUP'
            )
            """
        )
    op.execute("DROP TABLE retired_competition_games")
    op.execute("DROP TABLE retired_competition_teams")


def downgrade() -> None:
    op.execute(
        """
        INSERT INTO competition_settings (competition, is_enabled, created_at, updated_at)
        SELECT 'WORLD_CUP', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        WHERE NOT EXISTS (
            SELECT 1 FROM competition_settings WHERE competition = 'WORLD_CUP'
        )
        """
    )
