from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Team

NBA_TEAMS = [
    ("1610612737", "Atlanta Hawks", "ATL"),
    ("1610612738", "Boston Celtics", "BOS"),
    ("1610612751", "Brooklyn Nets", "BKN"),
    ("1610612766", "Charlotte Hornets", "CHA"),
    ("1610612741", "Chicago Bulls", "CHI"),
    ("1610612739", "Cleveland Cavaliers", "CLE"),
    ("1610612742", "Dallas Mavericks", "DAL"),
    ("1610612743", "Denver Nuggets", "DEN"),
    ("1610612765", "Detroit Pistons", "DET"),
    ("1610612744", "Golden State Warriors", "GSW"),
    ("1610612745", "Houston Rockets", "HOU"),
    ("1610612754", "Indiana Pacers", "IND"),
    ("1610612746", "LA Clippers", "LAC"),
    ("1610612747", "Los Angeles Lakers", "LAL"),
    ("1610612763", "Memphis Grizzlies", "MEM"),
    ("1610612748", "Miami Heat", "MIA"),
    ("1610612749", "Milwaukee Bucks", "MIL"),
    ("1610612750", "Minnesota Timberwolves", "MIN"),
    ("1610612740", "New Orleans Pelicans", "NOP"),
    ("1610612752", "New York Knicks", "NYK"),
    ("1610612760", "Oklahoma City Thunder", "OKC"),
    ("1610612753", "Orlando Magic", "ORL"),
    ("1610612755", "Philadelphia 76ers", "PHI"),
    ("1610612756", "Phoenix Suns", "PHX"),
    ("1610612757", "Portland Trail Blazers", "POR"),
    ("1610612758", "Sacramento Kings", "SAC"),
    ("1610612759", "San Antonio Spurs", "SAS"),
    ("1610612761", "Toronto Raptors", "TOR"),
    ("1610612762", "Utah Jazz", "UTA"),
    ("1610612764", "Washington Wizards", "WAS"),
]


def seed_teams_if_empty(db: Session) -> None:
    existing = db.scalar(select(Team.id).limit(1))
    if existing:
        return
    for external_team_id, name, abbreviation in NBA_TEAMS:
        db.add(
            Team(
                external_team_id=external_team_id,
                league="NBA",
                name=name,
                abbreviation=abbreviation,
            )
        )
    db.commit()
