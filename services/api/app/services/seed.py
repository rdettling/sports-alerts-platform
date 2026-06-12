from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Team, User
from app.services.leagues import ensure_league_settings

NBA_TEAMS = [
    ("1", "Atlanta Hawks", "ATL"),
    ("2", "Boston Celtics", "BOS"),
    ("3", "New Orleans Pelicans", "NO"),
    ("4", "Chicago Bulls", "CHI"),
    ("5", "Cleveland Cavaliers", "CLE"),
    ("6", "Dallas Mavericks", "DAL"),
    ("7", "Denver Nuggets", "DEN"),
    ("8", "Detroit Pistons", "DET"),
    ("9", "Golden State Warriors", "GS"),
    ("10", "Houston Rockets", "HOU"),
    ("11", "Indiana Pacers", "IND"),
    ("12", "LA Clippers", "LAC"),
    ("13", "Los Angeles Lakers", "LAL"),
    ("14", "Miami Heat", "MIA"),
    ("15", "Milwaukee Bucks", "MIL"),
    ("16", "Minnesota Timberwolves", "MIN"),
    ("17", "Brooklyn Nets", "BKN"),
    ("18", "New York Knicks", "NY"),
    ("19", "Orlando Magic", "ORL"),
    ("20", "Philadelphia 76ers", "PHI"),
    ("21", "Phoenix Suns", "PHX"),
    ("22", "Portland Trail Blazers", "POR"),
    ("23", "Sacramento Kings", "SAC"),
    ("24", "San Antonio Spurs", "SA"),
    ("25", "Oklahoma City Thunder", "OKC"),
    ("26", "Utah Jazz", "UTAH"),
    ("27", "Washington Wizards", "WSH"),
    ("28", "Toronto Raptors", "TOR"),
    ("29", "Memphis Grizzlies", "MEM"),
    ("30", "Charlotte Hornets", "CHA"),
]

MLB_TEAMS = [
    ("1", "Baltimore Orioles", "BAL"),
    ("2", "Boston Red Sox", "BOS"),
    ("3", "Los Angeles Angels", "LAA"),
    ("4", "Chicago White Sox", "CHW"),
    ("5", "Cleveland Guardians", "CLE"),
    ("6", "Detroit Tigers", "DET"),
    ("7", "Kansas City Royals", "KC"),
    ("8", "Milwaukee Brewers", "MIL"),
    ("9", "Minnesota Twins", "MIN"),
    ("10", "New York Yankees", "NYY"),
    ("11", "Athletics", "ATH"),
    ("12", "Seattle Mariners", "SEA"),
    ("13", "Texas Rangers", "TEX"),
    ("14", "Toronto Blue Jays", "TOR"),
    ("15", "Atlanta Braves", "ATL"),
    ("16", "Chicago Cubs", "CHC"),
    ("17", "Cincinnati Reds", "CIN"),
    ("18", "Houston Astros", "HOU"),
    ("19", "Los Angeles Dodgers", "LAD"),
    ("20", "Washington Nationals", "WSH"),
    ("21", "New York Mets", "NYM"),
    ("22", "Philadelphia Phillies", "PHI"),
    ("23", "Pittsburgh Pirates", "PIT"),
    ("24", "St. Louis Cardinals", "STL"),
    ("25", "San Diego Padres", "SD"),
    ("26", "San Francisco Giants", "SF"),
    ("27", "Colorado Rockies", "COL"),
    ("28", "Miami Marlins", "MIA"),
    ("29", "Arizona Diamondbacks", "ARI"),
    ("30", "Tampa Bay Rays", "TB"),
]


def seed_teams_if_empty(db: Session) -> None:
    ensure_league_settings(db)
    existing_nba = db.scalar(select(Team.id).where(Team.league == "NBA").limit(1))
    if not existing_nba:
        for external_team_id, name, abbreviation in NBA_TEAMS:
            db.add(
                Team(
                    external_team_id=external_team_id,
                    league="NBA",
                    name=name,
                    abbreviation=abbreviation,
                )
            )

    existing_mlb = db.scalar(select(Team.id).where(Team.league == "MLB").limit(1))
    if not existing_mlb:
        for external_team_id, name, abbreviation in MLB_TEAMS:
            db.add(
                Team(
                    external_team_id=external_team_id,
                    league="MLB",
                    name=name,
                    abbreviation=abbreviation,
                )
            )
    db.commit()


def ensure_bootstrap_admin(db: Session, email: str) -> None:
    normalized_email = email.strip().lower()
    if not normalized_email:
        return
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        db.add(User(email=normalized_email, role="admin"))
        db.commit()
        return
    if user.role != "admin":
        user.role = "admin"
        db.commit()
