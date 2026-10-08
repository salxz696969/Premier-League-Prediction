"""Club crests for the website.

Source: github.com/luukhopman/football-logos (PNG crests of the clubs in the top
25 European leagues, seasons 2021-22 onwards). Crests are trademarks of the
clubs; they are used here only to identify teams in a school project.

Clubs without a crest in that collection (older Premier League clubs such as
Bolton or Wigan, and lower-league cup opponents) keep the coloured badge with
the club's three-letter code.

Run:  uv run python -m eplpred.logos     (or scripts/01_download_data.py)
"""

from __future__ import annotations

import functools
import re
import unicodedata
import urllib.request
from urllib.parse import quote

from . import config

SOURCE = "https://raw.githubusercontent.com/luukhopman/football-logos/master/"
LOGO_DIR = config.RAW_DIR / "logos"

# Team name as it appears in our data -> file in the source repository.
LOGO_FILES = {
    '1899 Hoffenheim': 'logos/Germany - Bundesliga/TSG 1899 Hoffenheim.png',
    'Aalborg BK': 'history/2024-25/Denmark - Superliga/Aalborg BK.png',
    'AC Milan': 'logos/Italy - Serie A/AC Milan.png',
    'AC Sparta Praha': 'logos/Czech Republic - Chance Liga/AC Sparta Prague.png',
    'ACF Fiorentina': 'logos/Italy - Serie A/ACF Fiorentina.png',
    'AEK Athen': 'logos/Greece - Super League 1/AEK Athens.png',
    'AFC Ajax': 'history/2021-22/Netherlands - Eredivisie/Ajax.png',
    'AFC Bournemouth': 'logos/England - Premier League/AFC Bournemouth.png',
    'AJ Auxerre': 'logos/France - Ligue 1/AJ Auxerre.png',
    'Arsenal': 'logos/England - Premier League/Arsenal FC.png',
    'AS Monaco': 'logos/France - Ligue 1/AS Monaco.png',
    'AS Monaco FC': 'logos/France - Ligue 1/AS Monaco.png',
    'AS Roma': 'logos/Italy - Serie A/AS Roma.png',
    'Aston Villa': 'logos/England - Premier League/Aston Villa.png',
    'Atalanta': 'logos/Italy - Serie A/Atalanta BC.png',
    'Atalanta BC': 'logos/Italy - Serie A/Atalanta BC.png',
    'Athletic Club': 'history/2021-22/Spain - LaLiga/Athletic.png',
    'Atletico Madrid': 'logos/Spain - LaLiga/Atlético de Madrid.png',
    'Atlético Madrid': 'logos/Spain - LaLiga/Atlético de Madrid.png',
    'AZ Alkmaar': 'logos/Netherlands - Eredivisie/AZ Alkmaar.png',
    'Barcelona': 'logos/Spain - LaLiga/FC Barcelona.png',
    'Basel': 'history/2021-22/Switzerland - Super League/FC Basel.png',
    'Bayer 04 Leverkusen': 'logos/Germany - Bundesliga/Bayer 04 Leverkusen.png',
    'Bayer Leverkusen': 'logos/Germany - Bundesliga/Bayer 04 Leverkusen.png',
    'Bayern Munich': 'logos/Germany - Bundesliga/Bayern Munich.png',
    'Bayern München': 'logos/Germany - Bundesliga/Bayern Munich.png',
    'Besiktas': 'history/2021-22/Türkiye - Süper Lig/Besiktas.png',
    'Boavista': 'history/2024-25/Portugal - Liga Portugal/Boavista FC.png',
    'Bologna FC 1909': 'logos/Italy - Serie A/Bologna FC 1909.png',
    'Bor. Mönchengladbach': 'logos/Germany - Bundesliga/Borussia Mönchengladbach.png',
    'Borussia Dortmund': 'logos/Germany - Bundesliga/Borussia Dortmund.png',
    'Bournemouth': 'logos/England - Premier League/AFC Bournemouth.png',
    'Brentford': 'logos/England - Premier League/Brentford FC.png',
    'Brentford FC': 'logos/England - Premier League/Brentford FC.png',
    'Brighton & Hove Albion': 'logos/England - Premier League/Brighton & Hove Albion.png',
    'Brighton and Hove Albion': 'logos/England - Premier League/Brighton & Hove Albion.png',
    'BSC Young Boys': 'logos/Switzerland - Super League/BSC Young Boys.png',
    'Burnley': 'history/2025-26/England - Premier League/Burnley FC.png',
    'Burnley FC': 'history/2025-26/England - Premier League/Burnley FC.png',
    'Celta Vigo': 'logos/Spain - LaLiga/Celta de Vigo.png',
    'Celtic': 'logos/Scotland - Scottish Premiership/Celtic FC.png',
    'Celtic FC': 'logos/Scotland - Scottish Premiership/Celtic FC.png',
    'CFR Cluj': 'logos/Romania - SuperLiga/CFR Cluj.png',
    'Chelsea': 'logos/England - Premier League/Chelsea FC.png',
    'Club Atlético de Madrid': 'logos/Spain - LaLiga/Atlético de Madrid.png',
    'Club Brugge KV': 'logos/Belgium - Jupiler Pro League/Club Brugge KV.png',
    'Coventry City': 'logos/England - Premier League/Coventry City.png',
    'Crvena Zvezda': 'logos/Serbia - Super liga Srbije/Red Star Belgrade.png',
    'Crystal Palace': 'logos/England - Premier League/Crystal Palace.png',
    'CSKA Moskva': 'logos/Russia - Premier Liga/CSKA Moscow.png',
    'CSKA Sofia': 'logos/Bulgaria - efbet Liga/CSKA Sofia.png',
    'Debreceni VSC': 'history/2024-25/Hungary - Nemzeti Bajnokság/Debreceni VSC.png',
    'Deportivo La Coruna': 'logos/Spain - LaLiga/Deportivo A Coruña.png',
    'Dinamo Kiev': 'logos/Ukraine - Premier Liga/Dynamo Kyiv.png',
    'Dinamo Zagreb': 'logos/Croatia - SuperSport HNL/GNK Dinamo Zagreb.png',
    'Eintracht Frankfurt': 'logos/Germany - Bundesliga/Eintracht Frankfurt.png',
    'Everton': 'logos/England - Premier League/Everton FC.png',
    'FC Barcelona': 'logos/Spain - LaLiga/FC Barcelona.png',
    'FC Basel 1893': 'logos/Switzerland - Super League/FC Basel 1893.png',
    'FC Bayern München': 'logos/Germany - Bundesliga/Bayern Munich.png',
    'FC Internazionale Milano': 'logos/Italy - Serie A/Inter Milan.png',
    'FC København': 'logos/Denmark - Superliga/FC Copenhagen.png',
    'FC Midtjylland': 'logos/Denmark - Superliga/FC Midtjylland.png',
    'FC Nordsjælland': 'logos/Denmark - Superliga/FC Nordsjaelland.png',
    'FC Porto': 'logos/Portugal - Liga Portugal/FC Porto.png',
    'FC Schalke 04': 'logos/Germany - Bundesliga/FC Schalke 04.png',
    'FC Steaua Bucureşti': 'logos/Romania - SuperLiga/FCSB.png',
    'FC Twente': 'logos/Netherlands - Eredivisie/FC Twente Enschede.png',
    'FC Zürich': 'logos/Switzerland - Super League/FC Zürich.png',
    'FCSB': 'logos/Romania - SuperLiga/FCSB.png',
    'Fenerbahce': 'logos/Türkiye - Süper Lig/Fenerbahce.png',
    'Fenerbahçe': 'logos/Türkiye - Süper Lig/Fenerbahce.png',
    'Ferencvárosi TC': 'history/2024-25/Hungary - Nemzeti Bajnokság/Ferencvárosi TC.png',
    'Feyenoord': 'history/2021-22/Netherlands - Eredivisie/Feyenoord.png',
    'Feyenoord Rotterdam': 'logos/Netherlands - Eredivisie/Feyenoord Rotterdam.png',
    'FK Bodø/Glimt': 'history/2024-25/Norway - Eliteserien/FK Bodø Glimt.png',
    'FK Crvena Zvezda': 'logos/Serbia - Super liga Srbije/Red Star Belgrade.png',
    'FK Krasnodar': 'logos/Russia - Premier Liga/FC Krasnodar.png',
    'FK Shakhtar Donetsk': 'logos/Ukraine - Premier Liga/Shakhtar Donetsk.png',
    'Fulham': 'logos/England - Premier League/Fulham FC.png',
    'Fulham FC': 'logos/England - Premier League/Fulham FC.png',
    'Galatasaray': 'logos/Türkiye - Süper Lig/Galatasaray.png',
    'Galatasaray SK': 'logos/Türkiye - Süper Lig/Galatasaray.png',
    'Girona FC': 'history/2025-26/Spain - LaLiga/Girona FC.png',
    'Girondins Bordeaux': 'history/2021-22/France - Ligue 1/G. Bordeaux.png',
    'GNK Dinamo Zagreb': 'logos/Croatia - SuperSport HNL/GNK Dinamo Zagreb.png',
    'Granada CF': 'history/2023-24/Spain - LaLiga/Granada CF.png',
    'Hamburger SV': 'logos/Germany - Bundesliga/Hamburger SV.png',
    'Hull City': 'logos/England - Premier League/Hull City.png',
    'IF Elfsborg': 'logos/Sweden - Allsvenskan/IF Elfsborg.png',
    'Inter': 'logos/Italy - Serie A/Inter Milan.png',
    'Internazionale': 'logos/Italy - Serie A/Inter Milan.png',
    'Ipswich Town': 'logos/England - Premier League/Ipswich Town.png',
    'İstanbul Başakşehir': 'history/2022-23/Türkiye - Süper Lig/Istanbul Basaksehir FK.png',
    'Juventus': 'logos/Italy - Serie A/Juventus FC.png',
    'Juventus FC': 'logos/Italy - Serie A/Juventus FC.png',
    'Kobenhavn': 'logos/Denmark - Superliga/FC Copenhagen.png',
    'KRC Genk': 'logos/Belgium - Jupiler Pro League/KRC Genk.png',
    'LASK': 'logos/Austria - Bundesliga/LASK.png',
    'Lazio': 'history/2021-22/Italy - Serie A/Lazio.png',
    'Leeds United': 'logos/England - Premier League/Leeds United.png',
    'Legia Warszawa': 'logos/Poland - PKO BP Ekstraklasa/Legia Warszawa.png',
    'Leicester City': 'history/2024-25/England - Premier League/Leicester City.png',
    'Levski Sofia': 'logos/Bulgaria - efbet Liga/Levski Sofia.png',
    'Lille OSC': 'logos/France - Ligue 1/LOSC Lille.png',
    'Liverpool': 'logos/England - Premier League/Liverpool FC.png',
    'Lokomotiv Moskva': 'logos/Russia - Premier Liga/Lokomotiv Moscow.png',
    'Luton Town': 'history/2023-24/England - Premier League/Luton Town.png',
    'Maccabi Haifa': "logos/Israel - Ligat ha'Al/Maccabi Haifa.png",
    'Maccabi Tel Aviv': "logos/Israel - Ligat ha'Al/Maccabi Tel Aviv.png",
    'Malmö FF': 'logos/Sweden - Allsvenskan/Malmö FF.png',
    'Manchester City': 'logos/England - Premier League/Manchester City.png',
    'Manchester United': 'logos/England - Premier League/Manchester United.png',
    'Molde FK': 'logos/Norway - Eliteserien/Molde FK.png',
    'Montpellier HSC': 'history/2024-25/France - Ligue 1/Montpellier HSC.png',
    'Nantes': 'history/2025-26/France - Ligue 1/FC Nantes.png',
    'Newcastle United': 'logos/England - Premier League/Newcastle United.png',
    'Norwich City': 'history/2021-22/England - Premier League/Norwich.png',
    'Nottingham Forest': 'logos/England - Premier League/Nottingham Forest.png',
    'Olympiacos': 'history/2021-22/Greece - Super League 1/Olympiacos.png',
    'Olympiakos Piraeus': 'logos/Greece - Super League 1/Olympiacos Piraeus.png',
    'Olympique de Marseille': 'logos/France - Ligue 1/Olympique Marseille.png',
    'Olympique Lyon': 'logos/France - Ligue 1/Olympique Lyon.png',
    'Olympique Lyonnais': 'logos/France - Ligue 1/Olympique Lyon.png',
    'Olympique Marseille': 'logos/France - Ligue 1/Olympique Marseille.png',
    'Oţelul Galaţi': 'logos/Romania - SuperLiga/SC Otelul Galati.png',
    'PAE Olympiakos SFP': 'logos/Greece - Super League 1/Olympiacos Piraeus.png',
    'Panathinaikos': 'logos/Greece - Super League 1/Panathinaikos.png',
    'PAOK Saloniki': 'logos/Greece - Super League 1/PAOK Thessaloniki.png',
    'Paris Saint-Germain': 'logos/France - Ligue 1/Paris Saint-Germain.png',
    'Paris Saint-Germain FC': 'logos/France - Ligue 1/Paris Saint-Germain.png',
    'Partizan Belgrade': 'logos/Serbia - Super liga Srbije/FK Partizan Belgrade.png',
    'PFC Ludogorets Razgrad': 'logos/Bulgaria - efbet Liga/Ludogorets Razgrad.png',
    'PSV': 'logos/Netherlands - Eredivisie/PSV Eindhoven.png',
    'PSV Eindhoven': 'logos/Netherlands - Eredivisie/PSV Eindhoven.png',
    'Racing Club de Lens': 'logos/France - Ligue 1/RC Lens.png',
    'Rangers': 'logos/Scotland - Scottish Premiership/Rangers FC.png',
    'Rangers FC': 'logos/Scotland - Scottish Premiership/Rangers FC.png',
    'Rapid Wien': 'logos/Austria - Bundesliga/Rapid Vienna.png',
    'RB Leipzig': 'logos/Germany - Bundesliga/RB Leipzig.png',
    'RB Salzburg': 'history/2021-22/Austria - Bundesliga/RB Salzburg.png',
    'RCD Mallorca': 'history/2025-26/Spain - LaLiga/RCD Mallorca.png',
    'Real Betis': 'logos/Spain - LaLiga/Real Betis Balompié.png',
    'Real Madrid': 'logos/Spain - LaLiga/Real Madrid.png',
    'Real Madrid CF': 'logos/Spain - LaLiga/Real Madrid.png',
    'Real Sociedad': 'logos/Spain - LaLiga/Real Sociedad.png',
    'Rosenborg BK': 'logos/Norway - Eliteserien/Rosenborg BK.png',
    'Royal Antwerp FC': 'logos/Belgium - Jupiler Pro League/Royal Antwerp FC.png',
    'Royale Union Saint-Gilloise': 'history/2023-24/Belgium - Jupiler Pro League/Royale Union Saint Gilloise.png',
    'RSC Anderlecht': 'logos/Belgium - Jupiler Pro League/RSC Anderlecht.png',
    'SC Freiburg': 'logos/Germany - Bundesliga/SC Freiburg.png',
    'Schalke 04': 'logos/Germany - Bundesliga/FC Schalke 04.png',
    'Sevilla': 'logos/Spain - LaLiga/Sevilla FC.png',
    'Sevilla FC': 'logos/Spain - LaLiga/Sevilla FC.png',
    'Shakhtar Donetsk': 'logos/Ukraine - Premier Liga/Shakhtar Donetsk.png',
    'Sheffield United': 'history/2023-24/England - Premier League/Sheffield United.png',
    'SK Slavia Praha': 'logos/Czech Republic - Chance Liga/SK Slavia Prague.png',
    'SL Benfica': 'logos/Portugal - Liga Portugal/SL Benfica.png',
    'Slavia Praha': 'logos/Czech Republic - Chance Liga/SK Slavia Prague.png',
    'Southampton': 'history/2024-25/England - Premier League/Southampton FC.png',
    'Southampton FC': 'history/2024-25/England - Premier League/Southampton FC.png',
    'Sparta Praha': 'logos/Czech Republic - Chance Liga/AC Sparta Prague.png',
    'Spartak Moskva': 'logos/Russia - Premier Liga/Spartak Moscow.png',
    'Sport Lisboa e Benfica': 'logos/Portugal - Liga Portugal/SL Benfica.png',
    'Sporting Braga': 'logos/Portugal - Liga Portugal/SC Braga.png',
    'Sporting Clube de Portugal': 'logos/Portugal - Liga Portugal/Sporting CP.png',
    'Sporting CP': 'logos/Portugal - Liga Portugal/Sporting CP.png',
    'SSC Napoli': 'logos/Italy - Serie A/SSC Napoli.png',
    'Stade Rennais': 'logos/France - Ligue 1/Stade Rennais FC.png',
    'Standard Liege': 'logos/Belgium - Jupiler Pro League/Standard Liège.png',
    'Steaua Bucuresti': 'logos/Romania - SuperLiga/FCSB.png',
    'Sturm Graz': 'logos/Austria - Bundesliga/SK Sturm Graz.png',
    'Sunderland': 'logos/England - Premier League/Sunderland AFC.png',
    'Sunderland AFC': 'logos/England - Premier League/Sunderland AFC.png',
    'Thun': 'logos/Switzerland - Super League/FC Thun.png',
    'Tottenham Hotspur': 'logos/England - Premier League/Tottenham Hotspur.png',
    'Toulouse': 'logos/France - Ligue 1/FC Toulouse.png',
    'Toulouse FC': 'logos/France - Ligue 1/FC Toulouse.png',
    'TSC Bačka Topola': 'history/2025-26/Serbia - Super liga Srbije/FK TSC Backa Topola.png',
    'Twente': 'logos/Netherlands - Eredivisie/FC Twente Enschede.png',
    'Union Saint-Gilloise': 'logos/Belgium - Jupiler Pro League/Union Saint-Gilloise.png',
    'Valencia CF': 'logos/Spain - LaLiga/Valencia CF.png',
    'VfB Stuttgart': 'logos/Germany - Bundesliga/VfB Stuttgart.png',
    'VfL Wolfsburg': 'history/2025-26/Germany - Bundesliga/VfL Wolfsburg.png',
    'Viktoria Plzeň': 'logos/Czech Republic - Chance Liga/FC Viktoria Plzen.png',
    'Villarreal': 'logos/Spain - LaLiga/Villarreal CF.png',
    'Villarreal CF': 'logos/Spain - LaLiga/Villarreal CF.png',
    'Watford': 'history/2021-22/England - Premier League/Watford FC.png',
    'Watford FC': 'history/2021-22/England - Premier League/Watford FC.png',
    'Werder Bremen': 'logos/Germany - Bundesliga/SV Werder Bremen.png',
    'West Ham United': 'history/2025-26/England - Premier League/West Ham United.png',
    'Wolfsberger AC': 'logos/Austria - Bundesliga/Wolfsberger AC.png',
    'Wolverhampton': 'history/2025-26/England - Premier League/Wolverhampton Wanderers.png',
    'Wolverhampton Wanderers': 'history/2025-26/England - Premier League/Wolverhampton Wanderers.png',
    'Zalaegerszegi TE': 'history/2024-25/Hungary - Nemzeti Bajnokság/Zalaegerszegi TE FC.png',
    'Zenit St. Petersburg': 'logos/Russia - Premier Liga/Zenit St. Petersburg.png',
    'Zorya Lugansk': 'logos/Ukraine - Premier Liga/Zorya Lugansk.png',
}


def slug(team: str) -> str:
    """File name for a team's crest, from the crest's own file name (shared by aliases)."""
    stem = LOGO_FILES[team].rsplit("/", 1)[-1].removesuffix(".png")
    ascii_ = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_).strip("-")


@functools.cache
def logo_url(team: str) -> str | None:
    """URL path of the crest on the website, or None when we don't have one."""
    if team not in LOGO_FILES or not (LOGO_DIR / f"{slug(team)}.png").exists():
        return None
    return f"/logos/{slug(team)}.png"


def download(force: bool = False) -> None:
    logo_url.cache_clear()
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    done = set()
    for team, path in LOGO_FILES.items():
        target = LOGO_DIR / f"{slug(team)}.png"
        if target in done or (target.exists() and not force):
            continue
        with urllib.request.urlopen(SOURCE + quote(path), timeout=60) as response:
            target.write_bytes(response.read())
        done.add(target)
    print(f"Crests: {len(set(map(slug, LOGO_FILES)))} files in {LOGO_DIR.relative_to(config.ROOT)}")


if __name__ == "__main__":
    download()
