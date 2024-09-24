from collections import defaultdict
from dataclasses import dataclass
import json
import os
from os import path
import re

from tqdm import tqdm

# Given raw gamelogs, outputs a scoreboard & game summaries

# Uses tqdm (can be removed if needed)

RAW_DIRS = ["./raw/"]

GAMES_OUTPUT_DIR = "./games"
TEAMS_OUTPUT_DIR = "./teams"
README_PATH = "README.md"

EXCLUDE_TEAMS = set(["cool cids"])

PORT_SEARCH = re.compile("Connecting to server on port (\d+)")
FAILED_PORT_SEARCH = re.compile("Error: Command failed:\s*.*\s+serve\s+(\d+)")

@dataclass
class Game:
    id: str
    teams: tuple[str, str]
    logs: tuple[str, str]
    wins: tuple[float, float]
    engine_log: str
    game_log: object

games: dict[tuple[str,str], Game] = dict()
teams: set[str] = set()


def read_file(path):
    with open(path, "r", encoding="utf-8") as file:
        return file.read()

def write_file(path, text):
    with open(path, "w", encoding="utf-8") as file:
        return file.write(text)
    
game_paths = []

for raw_dir in RAW_DIRS:
    for game_dir in os.listdir(raw_dir):
        game_paths.append(path.join(raw_dir, game_dir))

can_proceed = True

print("Processing games...")
for game_path in tqdm(game_paths):
    game_id = os.path.basename(game_path)
    bot_logs_path = path.join(game_path, "bots")
    bot_logs = os.listdir(bot_logs_path)

    game_log = read_file(path.join(game_path, "engine", "gamelog.json"))
    parsed_game_log = json.loads(game_log)
    wins = parsed_game_log["wins"]
    game_engine_log = read_file(path.join(game_path, "engine", "engine.log"))

    game_bot_teams = dict()
    game_bot_logs = dict()
    for bot_log in bot_logs:
        team_name = bot_log.removesuffix(".log")
        log = read_file(path.join(bot_logs_path, bot_log))

        match_connecting = PORT_SEARCH.search(log)
        if match_connecting:
            port = match_connecting.group(1)
        else:
            match_error = FAILED_PORT_SEARCH.search(log)
            if match_error:
                port = match_error.group(1)
            else:
                port = None

        if port == None:
            raise RuntimeError(f"Invalid port for team {team_name}")

        if team_name not in teams:
            teams.add(team_name)
        
        if port == "9001":
            game_bot_teams[0] = team_name
            game_bot_logs[0] = log
        else:
            game_bot_teams[1] = team_name
            game_bot_logs[1] = log

    if 0 not in game_bot_teams or 1 not in game_bot_teams:
        can_proceed = False
        print(f"Bad game file: {game_path}")
        continue
    pairing = (game_bot_teams[0], game_bot_teams[1])
    reverse_pairing = (game_bot_teams[1], game_bot_teams[0])

    if pairing not in games and reverse_pairing not in games:
        games[pairing] = Game(
            game_id,
            pairing,
            (game_bot_logs[0], game_bot_logs[1]),
            wins,
            game_engine_log,
            parsed_game_log
        )

if not can_proceed:
    exit(1)

print(f"De-duped {len(game_paths)} games into {len(games)} pairings")

games = dict(filter(
    lambda entry: entry[1].teams[0] not in EXCLUDE_TEAMS and
    entry[1].teams[1] not in EXCLUDE_TEAMS, 
    games.items())
)
teams = set(filter(lambda team: team not in EXCLUDE_TEAMS, teams))

print(f"Excluded teams to reduce total games to {len(games)}")

missing = set()

for team1 in teams:
    for team2 in teams:
        if team1 == team2:
            continue

        pairing = (team1, team2)
        reverse_pairing = (team2, team1)

        if pairing not in games and reverse_pairing not in games:
            if pairing not in missing and reverse_pairing not in missing:
                missing.add(pairing)
                
if len(missing) > 0:
    print(f"Warning: There are {len(missing)} missing pairs: {missing}")

writes = dict()

print("Summarizing games...")
def add_links(summary: str, team0, team1, prefix=None):
    if not prefix:
        prefix = ""
        summary = re.sub(r"^## (.*) vs (.*)", fr"## [\1](<../../\1/README.md>) vs [\2](<../../\2/README.md>)", summary)
    else:
        prefix += "/"
        summary = re.sub(r"^## (.*)", fr"## [\1](<{prefix}README.md>)", summary)
    return summary.replace("<links>",
        f"[gamelog](<{prefix}gamelog.json>) | [engine log](<{prefix}engine>) | " + \
        f"[{team0} log](<{prefix}{team0}>) | [{team1} log](<{prefix}{team1}>)")

team_summaries = defaultdict(list)

for [team0, team1], game in tqdm(games.items()):
    team0_wins, team1_wins = game.wins
    result = "Draw!" if team0_wins == team1_wins else (f"{team0} wins!" if team0_wins > team1_wins else f"{team1} wins!")

    stats = game.game_log["stats"]
    team0_stats = (stats["remainingPlaneScores"][0], stats["totalSpends"][0], stats["dealtDamages"][0])
    team1_stats = (stats["remainingPlaneScores"][1], stats["totalSpends"][1], stats["dealtDamages"][1])
    team0_score, team0_spent, team0_damage = team0_stats
    team1_score, team1_spent, team1_damage = team1_stats

    team0_wins = f"+{team0_wins}"
    team1_wins = f"+{team1_wins}"

    team0_pad = max(len(team0), len(str(team0_wins)), max(*map(lambda stat: len(str(stat)), team0_stats)))
    team1_pad = max(len(team1), len(str(team1_wins)), max(*map(lambda stat: len(str(stat)), team1_stats)))

    summary = f"## {team0} vs {team1}\n" + \
        f"### {result}\n\n" + \
        f"<links>\n\n" + \
        f"|              | {team0:{team0_pad}} | {team1:{team1_pad}} |\n" + \
        f"| ------------ | {'-' * team0_pad} | {'-' * team1_pad} |\n" + \
        f"| Wins         | {team0_wins:{'>'}{team0_pad}} | {team1_wins:{'>'}{team1_pad}} |\n" + \
        f"| Score        | {team0_score:{team0_pad}} | {team1_score:{team1_pad}} |\n" + \
        f"| Points Spent | {team0_spent:{team0_pad}} | {team1_spent:{team1_pad}} |\n" + \
        f"| Damage       | {team0_damage:{team0_pad}} | {team1_damage:{team1_pad}} |\n"
    
    team_summaries[team0].append((team0_wins, team1, team0, team1, summary))
    team_summaries[team1].append((team1_wins, team0, team0, team1, summary))

    game_summary = add_links(summary, team0, team1)
    
    output_game_log = json.dumps(game.game_log, indent=4)

    dirs = [path.join(GAMES_OUTPUT_DIR, game.id), path.join(TEAMS_OUTPUT_DIR, team0, team1), path.join(TEAMS_OUTPUT_DIR, team1, team0)]
    for dir in dirs:
        writes[path.join(dir, team0)] = game.logs[0]
        writes[path.join(dir, team1)] = game.logs[1]
        writes[path.join(dir, "engine")] = game.engine_log
        writes[path.join(dir, "gamelog.json")]= output_game_log
        writes[path.join(dir, "README.md")] = game_summary

# Get scores
print("Computing scoreboard...")
scoring = defaultdict(float)
for [team0, team1], game in games.items():
    scoring[team0] += game.wins[0]
    scoring[team1] += game.wins[1]

scoreboard = sorted(scoring.items(), key=lambda entry: entry[1], reverse=True)
scoreboard_tie_adjusted = []

prev_score = None
pos = 0
for i, [team, score] in enumerate(scoreboard):
    if score != prev_score:
        pos = i + 1
    
    scoreboard_tie_adjusted.append((pos, team, score))
    prev_score = score

scoreboard_with_links = list(map(lambda entry: (entry[0], f"[{entry[1]}](<teams/{entry[1]}/README.md>)", entry[2]), scoreboard_tie_adjusted))

pos_pad = len(str(pos))
team_pad = max(*map(lambda team: len(team), map(lambda entry: entry[1], scoreboard_with_links)))
wins_pad = max(len(str(scoreboard[0][1])), len("Wins"))

readme_text = "# Scoring\n" + \
    f"| {' ' * pos_pad} | {'Team':{team_pad}} | {'Wins':{wins_pad}} |\n" + \
    f"| {'-' * pos_pad} | {'-' * team_pad} | {'-' * wins_pad} |\n" + \
    "\n".join(f"| {pos:{pos_pad}} | {team:{team_pad}} | {wins:{wins_pad}} |" for pos, team, wins in scoreboard_with_links) + "\n"

writes[README_PATH] = readme_text

print("Summarizing teams...")
for team, game_summaries in tqdm(team_summaries.items()):
    wins = len(list(filter(lambda summary: summary[0] == "+1", game_summaries)))
    draws = len(list(filter(lambda summary: summary[0] == "+0.5", game_summaries)))
    loses = len(list(filter(lambda summary: summary[0] == "+0", game_summaries)))

    for this_placement, this_team, this_score in scoreboard_tie_adjusted:
        if this_team == team:
            score = this_score
            placement = this_placement
            break

    team_summary = f"# [{team}](../../README.md) Summary\n" + \
        f"Placed #{placement} with {score} wins\n" + \
        f"- Played against {len(game_summaries)} other teams\n" + \
        f"- {wins} wins (+{wins})\n" + \
        f"- {draws} draws (+{draws * 0.5})\n" + \
        f"- {loses} loses (+0)\n" + \
        "\n\n".join(add_links(summary, team0, team1, other_team) for _, other_team, team0, team1, summary in game_summaries) + "\n"
    writes[path.join(TEAMS_OUTPUT_DIR, team, "README.md")] = team_summary
    
print("Writing files...")
for filepath, text in tqdm(writes.items()):
    dir = path.dirname(filepath)
    if len(dir) > 0 and not path.exists(dir):
        os.makedirs(dir, exist_ok=True)
    write_file(filepath, text)


print("Done")
