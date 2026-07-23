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

MLS_TEAMS = [
    ("18418", "Atlanta United FC", "ATL"),
    ("20906", "Austin FC", "ATX"),
    ("9720", "CF Montréal", "MTL"),
    ("21300", "Charlotte FC", "CLT"),
    ("182", "Chicago Fire FC", "CHI"),
    ("184", "Colorado Rapids", "COL"),
    ("183", "Columbus Crew", "CLB"),
    ("193", "D.C. United", "DC"),
    ("18267", "FC Cincinnati", "CIN"),
    ("185", "FC Dallas", "DAL"),
    ("6077", "Houston Dynamo FC", "HOU"),
    ("20232", "Inter Miami CF", "MIA"),
    ("187", "LA Galaxy", "LA"),
    ("18966", "LAFC", "LAFC"),
    ("17362", "Minnesota United FC", "MIN"),
    ("18986", "Nashville SC", "NSH"),
    ("189", "New England Revolution", "NE"),
    ("17606", "New York City FC", "NYC"),
    ("12011", "Orlando City SC", "ORL"),
    ("10739", "Philadelphia Union", "PHI"),
    ("9723", "Portland Timbers", "POR"),
    ("4771", "Real Salt Lake", "RSL"),
    ("190", "Red Bull New York", "RBNY"),
    ("22529", "San Diego FC", "SD"),
    ("191", "San Jose Earthquakes", "SJ"),
    ("9726", "Seattle Sounders FC", "SEA"),
    ("186", "Sporting Kansas City", "SKC"),
    ("21812", "St. Louis CITY SC", "STL"),
    ("7318", "Toronto FC", "TOR"),
    ("9727", "Vancouver Whitecaps", "VAN"),
]

WORLD_CUP_TEAMS = [
    ("624", "Algeria", "ALG"),
    ("202", "Argentina", "ARG"),
    ("628", "Australia", "AUS"),
    ("474", "Austria", "AUT"),
    ("459", "Belgium", "BEL"),
    ("452", "Bosnia-Herzegovina", "BIH"),
    ("205", "Brazil", "BRA"),
    ("206", "Canada", "CAN"),
    ("2597", "Cape Verde", "CPV"),
    ("208", "Colombia", "COL"),
    ("2850", "Congo DR", "COD"),
    ("477", "Croatia", "CRO"),
    ("11678", "Curacao", "CUW"),
    ("450", "Czechia", "CZE"),
    ("209", "Ecuador", "ECU"),
    ("2620", "Egypt", "EGY"),
    ("448", "England", "ENG"),
    ("478", "France", "FRA"),
    ("481", "Germany", "GER"),
    ("4469", "Ghana", "GHA"),
    ("2654", "Haiti", "HAI"),
    ("469", "Iran", "IRN"),
    ("4375", "Iraq", "IRQ"),
    ("4789", "Ivory Coast", "CIV"),
    ("627", "Japan", "JPN"),
    ("2917", "Jordan", "JOR"),
    ("203", "Mexico", "MEX"),
    ("2869", "Morocco", "MAR"),
    ("449", "Netherlands", "NED"),
    ("2666", "New Zealand", "NZL"),
    ("464", "Norway", "NOR"),
    ("2659", "Panama", "PAN"),
    ("210", "Paraguay", "PAR"),
    ("482", "Portugal", "POR"),
    ("4398", "Qatar", "QAT"),
    ("655", "Saudi Arabia", "KSA"),
    ("580", "Scotland", "SCO"),
    ("654", "Senegal", "SEN"),
    ("467", "South Africa", "RSA"),
    ("451", "South Korea", "KOR"),
    ("164", "Spain", "ESP"),
    ("466", "Sweden", "SWE"),
    ("475", "Switzerland", "SUI"),
    ("659", "Tunisia", "TUN"),
    ("465", "Turkiye", "TUR"),
    ("660", "United States", "USA"),
    ("212", "Uruguay", "URU"),
    ("2570", "Uzbekistan", "UZB"),
]

TEAM_SEEDS_BY_LEAGUE = {
    "NBA": NBA_TEAMS,
    "MLB": MLB_TEAMS,
    "MLS": MLS_TEAMS,
    "WORLD_CUP": WORLD_CUP_TEAMS,
}


def seed_teams_if_empty(db: Session) -> None:
    ensure_league_settings(db)
    for league, teams in TEAM_SEEDS_BY_LEAGUE.items():
        if db.scalar(select(Team.id).where(Team.league == league).limit(1)):
            continue
        for external_team_id, name, abbreviation in teams:
            db.add(
                Team(
                    external_team_id=external_team_id,
                    league=league,
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
