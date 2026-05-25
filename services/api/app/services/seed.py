from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Team, User

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

MLB_TEAMS = [
    ("ARI", "Arizona Diamondbacks", "ARI"),
    ("ATL", "Atlanta Braves", "ATL"),
    ("BAL", "Baltimore Orioles", "BAL"),
    ("BOS", "Boston Red Sox", "BOS"),
    ("CHC", "Chicago Cubs", "CHC"),
    ("CWS", "Chicago White Sox", "CWS"),
    ("CIN", "Cincinnati Reds", "CIN"),
    ("CLE", "Cleveland Guardians", "CLE"),
    ("COL", "Colorado Rockies", "COL"),
    ("DET", "Detroit Tigers", "DET"),
    ("HOU", "Houston Astros", "HOU"),
    ("KC", "Kansas City Royals", "KC"),
    ("LAA", "Los Angeles Angels", "LAA"),
    ("LAD", "Los Angeles Dodgers", "LAD"),
    ("MIA", "Miami Marlins", "MIA"),
    ("MIL", "Milwaukee Brewers", "MIL"),
    ("MIN", "Minnesota Twins", "MIN"),
    ("NYM", "New York Mets", "NYM"),
    ("NYY", "New York Yankees", "NYY"),
    ("OAK", "Athletics", "OAK"),
    ("PHI", "Philadelphia Phillies", "PHI"),
    ("PIT", "Pittsburgh Pirates", "PIT"),
    ("SD", "San Diego Padres", "SD"),
    ("SF", "San Francisco Giants", "SF"),
    ("SEA", "Seattle Mariners", "SEA"),
    ("STL", "St. Louis Cardinals", "STL"),
    ("TB", "Tampa Bay Rays", "TB"),
    ("TEX", "Texas Rangers", "TEX"),
    ("TOR", "Toronto Blue Jays", "TOR"),
    ("WSH", "Washington Nationals", "WSH"),
]


def seed_teams_if_empty(db: Session) -> None:
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
