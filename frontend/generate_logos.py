import urllib.request
import urllib.parse
import json
import ssl
import sys

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

teams = ['ac milan', 'angers', 'arsenal', 'aston villa', 'atalanta', 'athletic club', 'atletico madrid', 'augsburg', 'auxerre', 'barcelona', 'bayer leverkusen', 'bayern', 'bologna', 'borussia dortmund', 'borussia m.gladbach', 'bournemouth', 'brentford', 'brest', 'brighton', 'burnley', 'cagliari', 'celta vigo', 'chelsea', 'como', 'cremonese', 'crystal palace', 'deportivo alaves', 'eintracht frankfurt', 'elche', 'espanyol', 'everton', 'fc heidenheim', 'fc koln', 'fiorentina', 'freiburg', 'fulham', 'genoa', 'getafe', 'girona', 'hamburger sv', 'hoffenheim', 'inter', 'juventus', 'lazio', 'le havre', 'lecce', 'leeds', 'lens', 'levante', 'lille', 'liverpool', 'lorient', 'lyon', 'mainz 05', 'mallorca', 'man city', 'man utd', 'marseille', 'metz', 'monaco', 'nantes', 'napoli', 'newcastle', 'nice', 'nottingham forest', 'osasuna', 'paris fc', 'paris saint germain', 'parma calcio 1913', 'pisa', 'rayo vallecano', 'rb leipzig', 'real betis', 'real madrid', 'real oviedo', 'real sociedad', 'rennes', 'roma', 'sassuolo', 'sevilla', 'spurs', 'st. pauli', 'strasbourg', 'sunderland', 'torino', 'tottenham', 'toulouse', 'udinese', 'union berlin', 'valencia', 'verona', 'vfb stuttgart', 'villarreal', 'werder bremen', 'west ham', 'wolfsburg', 'wolves']

output = {}

for team in teams:
    url = f'https://apigw.fotmob.com/searchapi/suggest?term={urllib.parse.quote(team)}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx) as r:
            data = json.loads(r.read())
            team_id = None
            if 'teamSuggest' in data and len(data['teamSuggest']) > 0:
                opts = data['teamSuggest'][0].get('options', [])
                if opts:
                    team_id = opts[0].get('payload', {}).get('id')
            if team_id:
                output[team] = f'https://images.fotmob.com/image_resources/logo/teamlogo/{team_id}.png'
    except Exception as e:
        pass

# Hardcoded overrides for perfect rendering
output.update({
  'barcelona': 'https://upload.wikimedia.org/wikipedia/en/4/47/FC_Barcelona_%28crest%29.svg',
  'real madrid': 'https://upload.wikimedia.org/wikipedia/en/5/56/Real_Madrid_CF.svg',
  'arsenal': 'https://upload.wikimedia.org/wikipedia/en/5/53/Arsenal_FC.svg',
  'liverpool': 'https://upload.wikimedia.org/wikipedia/en/0/0c/Liverpool_FC.svg'
})

js_file = r'e:\Personal Projects\xG-app\frontend\src\utils\logos.js'

js_content = f'''export const TEAM_LOGOS = {json.dumps(output, indent=2)};

export function getTeamLogo(teamName) {{
  const normalized = Object.keys(TEAM_LOGOS).find(key => 
    teamName.toLowerCase().includes(key.toLowerCase())
  );
  
  if (normalized) {{
    return TEAM_LOGOS[normalized];
  }}

  // Beautiful monogram fallback securely using ui-avatars.
  return `https://ui-avatars.com/api/?name=${{encodeURIComponent(teamName)}}&background=111827&color=fff&rounded=true&bold=true&format=svg`;
}}
'''

with open(js_file, 'w', encoding='utf-8') as f:
    f.write(js_content)
    
print('Successfully generated logos.js')
