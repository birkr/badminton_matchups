from flask import Flask, render_template, request, redirect, url_for
import json
from itertools import combinations, product
import os

app = Flask(__name__)

# Define player class
class Player:
    def __init__(self, name, gender, skill, preferences, present='yes'):
        self.name = name
        self.gender = gender  # 'M' or 'F'
        self.skill = skill
        self.preferences = preferences  # List of preferred match types ('MD', 'WD', 'XD', 'MS', 'WS')
        self.present = present  # 'yes' if the player is present, 'no' otherwise

    def __repr__(self):
        return f"{self.name}({self.gender}, Skill:{self.skill})"

    def to_dict(self):
        return {
            'name': self.name,
            'gender': self.gender,
            'skill': self.skill,
            'preferences': self.preferences,
            'present': self.present

        }

    @staticmethod
    def from_dict(data):
        return Player(
            name=data['name'],
            gender=data['gender'],
            skill=data['skill'],
            preferences=data['preferences'],
            present=data.get('present', 'yes')  # Default to 'yes' if not present
        )

# Define team class
class Team:
    def __init__(self, players, match_type):
        self.players = players  # List of one or two Player objects
        self.match_type = match_type  # 'MD', 'WD', 'XD', 'MS', 'WS'
        self.skill = sum(player.skill for player in players)
        self.player_names = set(player.name for player in players)

    def __repr__(self):
        player_names = " & ".join(player.name for player in self.players)
        return f"Team({player_names}, {self.match_type}, Skill:{self.skill})"

# Define match class
class Match:
    def __init__(self, team1, team2, skill_diff):
        self.team1 = team1  # Team object
        self.team2 = team2  # Team object
        self.skill_diff = skill_diff
        self.players = self.team1.player_names.union(self.team2.player_names)

    def __repr__(self):
        return f"Match({self.team1} vs {self.team2}, Skill Diff:{self.skill_diff})"

    def to_dict(self):
        return {
            'team1': [player.name for player in self.team1.players],
            'team2': [player.name for player in self.team2.players],
            'match_type': self.team1.match_type,
            'skill_diff': self.skill_diff
        }

    @staticmethod
    def from_dict(data, players_dict):
        team1_players = [players_dict[name] for name in data['team1']]
        team2_players = [players_dict[name] for name in data['team2']]
        team1 = Team(team1_players, data['match_type'])
        team2 = Team(team2_players, data['match_type'])
        match = Match(team1, team2, data['skill_diff'])
        return match

def generate_possible_teams(players):
    teams = []

    # Include singles and doubles matches
    match_types = ['MD', 'WD', 'XD', 'MS', 'WS']

    for match_type in match_types:
        if match_type == 'MD':
            eligible_players = [p for p in players if p.gender == 'M' and 'MD' in p.preferences]
            player_combinations = list(combinations(eligible_players, 2))
        elif match_type == 'WD':
            eligible_players = [p for p in players if p.gender == 'F' and 'WD' in p.preferences]
            player_combinations = list(combinations(eligible_players, 2))
        elif match_type == 'XD':
            eligible_males = [p for p in players if p.gender == 'M' and 'XD' in p.preferences]
            eligible_females = [p for p in players if p.gender == 'F' and 'XD' in p.preferences]
            player_combinations = list(product(eligible_males, eligible_females))
        elif match_type == 'MS':
            eligible_players = [p for p in players if p.gender == 'M' and 'MS' in p.preferences]
            player_combinations = [(player,) for player in eligible_players]
        elif match_type == 'WS':
            eligible_players = [p for p in players if p.gender == 'F' and 'WS' in p.preferences]
            player_combinations = [(player,) for player in eligible_players]
        else:
            continue
        for players_pair in player_combinations:
            team = Team(players_pair, match_type)
            teams.append(team)

    return teams

def find_best_matches(teams, num_courts, match_history, rounds_between_repeats):
    from itertools import combinations

    # Generate all possible matches
    matches = []
    for team1, team2 in combinations(teams, 2):
        if team1.match_type != team2.match_type:
            continue
        if team1.player_names.isdisjoint(team2.player_names):
            # Check if this matchup has occurred recently
            matchup_key = frozenset(team1.player_names.union(team2.player_names))
            if matchup_key in match_history and match_history[matchup_key] < rounds_between_repeats:
                continue
            match = Match(team1, team2, abs(team1.skill - team2.skill))
            matches.append(match)

    # Sort matches by skill difference
    matches.sort(key=lambda x: x.skill_diff)

    # Select matches without overlapping players
    selected_matches = []
    assigned_players = set()
    for match in matches:
        if len(selected_matches) >= num_courts:
            break
        if assigned_players & match.players:
            continue
        selected_matches.append(match)
        assigned_players.update(match.players)

    # Update match history
    for matchup in match_history:
        match_history[matchup] += 1
    for match in selected_matches:
        matchup_key = frozenset(match.team1.player_names.union(match.team2.player_names))
        match_history[matchup_key] = 0

    return selected_matches

def load_players_from_json(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, 'r') as file:
        data = json.load(file)
    players = [Player.from_dict(player_data) for player_data in data]
    return players

def save_players_to_json(players, filename):
    with open(filename, 'w') as file:
        json.dump([player.to_dict() for player in players], file)

def save_match_history(match_history, filename):
    # Convert the frozenset keys to sorted, semi-colon-separated strings for JSON serialization
    serializable_history = {}
    for matchup, count in match_history.items():
        # Convert frozenset to a sorted list, then join into a string
        key = ';'.join(sorted(matchup))
        serializable_history[key] = count
    with open(filename, 'w') as file:
        json.dump(serializable_history, file)

def load_match_history(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename, 'r') as file:
        data = json.load(file)
    match_history = {}
    for key, count in data.items():
        # Split the string back into a list and convert to frozenset
        matchup = frozenset(key.split(';'))
        match_history[matchup] = count
    return match_history

def generate_round(players, num_courts, rounds_between_repeats):
    present_players = [player for player in players if player.present == 'yes']
    
    if not present_players:
        return [], []  # No matches if no players are present

    match_history_file = 'match_history.json'
    match_history = load_match_history(match_history_file)

    teams = generate_possible_teams(present_players)
    matches = find_best_matches(teams, num_courts, match_history, rounds_between_repeats)
    assigned_players = set()
    if matches:
        # Save match history
        save_match_history(match_history, match_history_file)
        # Collect assigned players
        for match in matches:
            assigned_players.update(match.players)
    else:
        matches = []
    # Identify unassigned players
    unassigned_players = [player for player in present_players if player.name not in assigned_players]
    return matches, unassigned_players

# Flask Routes

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/players', methods=['GET', 'POST'])
def view_players():
    players = load_players_from_json('players.json')

    if request.method == 'POST':
        # Iterate over the form data and update the players
        for player in players:
            player.gender = request.form.get(f'gender_{player.name}')
            player.skill = int(request.form.get(f'skill_{player.name}'))
            player.preferences = request.form.getlist(f'preferences_{player.name}')
            # Handle presence checkbox
            player.present = 'yes' if request.form.get(f'present_{player.name}') else 'no'

        # Save the updated players list to the JSON file (if needed)
        save_players_to_json(players, 'players.json')
        return redirect(url_for('view_players'))

    return render_template('players.html', players=players)

@app.route('/add_player', methods=['GET', 'POST'])
def add_player():
    if request.method == 'POST':
        name = request.form['name']
        gender = request.form['gender']
        skill = int(request.form['skill'])
        preferences = request.form.getlist('preferences')
        # Load existing players
        players = load_players_from_json('players.json')
        # Check if player name already exists
        if any(player.name == name for player in players):
            error = "A player with that name already exists."
            return render_template('add_player.html', error=error)
        # Create new player
        new_player = Player(name, gender, skill, preferences)
        players.append(new_player)
        # Save to JSON
        save_players_to_json(players, 'players.json')
        return redirect(url_for('view_players'))
    return render_template('add_player.html')

@app.route('/generate_matches', methods=['GET', 'POST'])
def generate_matches():
    players = load_players_from_json('players.json')
    
    # Filter players based on their present status (use only players marked as 'yes')
    present_players = [player for player in players if player.present == 'yes']
    
    if request.method == 'POST':
        num_courts = int(request.form.get('num_courts', 10))  # Default to 10 if no input
        rounds_between_repeats = int(request.form.get('rounds_between_repeats', 3))  # Optional setting
        # Pass the present players to generate the matches
        matches, unassigned_players = generate_round(present_players, num_courts, rounds_between_repeats)
        return render_template('matches.html', matches=matches, unassigned_players=unassigned_players)
    else:
        return render_template('select_players.html')

@app.route('/clear_history')
def clear_history():
    if os.path.exists('match_history.json'):
        os.remove('match_history.json')
    return redirect(url_for('index'))

@app.route('/remove_player/<name>', methods=['POST'])
def remove_player(name):
    players = load_players_from_json('players.json')
    
    # Filter out the player with the given name
    players = [player for player in players if player.name != name]
    
    # Save the updated list back to the JSON file
    save_players_to_json(players, 'players.json')
    
    return redirect(url_for('view_players'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
