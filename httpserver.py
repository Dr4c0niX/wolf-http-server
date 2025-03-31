#wolf-http-server/httpserver.py
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import psycopg2
from psycopg2.extras import RealDictCursor

# Connexion à la base de données
conn = psycopg2.connect(
    dbname="wolf_game",
    user="wolf_admin",
    password="motdepasse_secure",
    host="db",
    port="5432"
)
cursor = conn.cursor(cursor_factory=RealDictCursor)

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/list_parties':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            # Récupérer les parties depuis la base de données
            cursor.execute("SELECT id_party, title_party FROM parties WHERE is_started = FALSE AND is_finished = FALSE")
            parties = cursor.fetchall()
            parties_data = {
                "id_parties": [party['id_party'] for party in parties],
                "parties_info": {str(party['id_party']): {"title_party": party['title_party']} for party in parties}
            }

            self.wfile.write(json.dumps(parties_data).encode('utf-8'))
        
        elif self.path.startswith('/party_details/'):
            party_id = self.path.split('/')[-1]
            try:
                party_id = int(party_id)
                cursor.execute("""
                    SELECT p.id_party, p.title_party, p.grid_size, p.max_players, p.max_turns, p.turn_duration,
                           COUNT(CASE WHEN r.role_name = 'villager' THEN 1 END) as villagers_count,
                           COUNT(CASE WHEN r.role_name = 'werewolf' THEN 1 END) as werewolves_count,
                           COUNT(pip.id_player) as current_players
                    FROM parties p
                    LEFT JOIN players_in_parties pip ON p.id_party = pip.id_party
                    LEFT JOIN roles r ON pip.id_role = r.id_role
                    WHERE p.id_party = %s
                    GROUP BY p.id_party
                """, (party_id,))
                party = cursor.fetchone()
                
                if party:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps(dict(party)).encode('utf-8'))
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Partie non trouvée"}).encode('utf-8'))
            except ValueError:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "ID de partie invalide"}).encode('utf-8'))

        elif self.path == '/all_parties_details':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            cursor.execute("""
                SELECT p.id_party, p.title_party, p.grid_size, p.max_players, p.max_turns, p.turn_duration,
                       COUNT(CASE WHEN r.role_name = 'villager' THEN 1 END) as villagers_count,
                       COUNT(CASE WHEN r.role_name = 'werewolf' THEN 1 END) as werewolves_count,
                       COUNT(pip.id_player) as current_players
                FROM parties p
                LEFT JOIN players_in_parties pip ON p.id_party = pip.id_party
                LEFT JOIN roles r ON pip.id_role = r.id_role
                WHERE p.is_started = FALSE AND p.is_finished = FALSE
                GROUP BY p.id_party
            """)
            parties = cursor.fetchall()
            parties_dict = {str(party['id_party']): dict(party) for party in parties}
            
            self.wfile.write(json.dumps(parties_dict).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)

        if self.path == '/subscribe':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            # Logique pour s'inscrire à une partie
            player = data["player"]
            id_party = data["id_party"]
            role_preference = data.get("role_preference", "villageois")

            # Vérifier si le joueur existe, sinon le créer
            cursor.execute("SELECT id_player FROM players WHERE pseudo = %s", (player,))
            result = cursor.fetchone()
            if result is None:
                cursor.execute("INSERT INTO players (pseudo) VALUES (%s) RETURNING id_player", (player,))
                id_player = cursor.fetchone()['id_player']
            else:
                id_player = result['id_player']

            # Déterminer le rôle (pour simplifier, utilisons le rôle préféré)
            role_name = 'villager' if role_preference == 'villageois' else 'werewolf'
            cursor.execute("SELECT id_role FROM roles WHERE role_name = %s", (role_name,))
            id_role = cursor.fetchone()['id_role']

            # Inscrire le joueur à la partie
            cursor.execute("INSERT INTO players_in_parties (id_party, id_player, id_role) VALUES (%s, %s, %s)", 
                          (id_party, id_player, id_role))
            conn.commit()

            response = {
                "status": "OK",
                "response": {
                    "role": role_preference,
                    "id_player": id_player
                }
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        elif self.path == '/create_solo_game':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            player_name = data["player_name"]
            role_preference = data.get("role_preference", "villageois")
            
            # Créer une nouvelle partie
            cursor.execute("""
                INSERT INTO parties (title_party, grid_size, max_players, max_turns, turn_duration)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id_party
            """, (f"Partie solo de {player_name}", 10, 8, 30, 60))
            
            id_party = cursor.fetchone()['id_party']
            
            # Vérifier si le joueur existe, sinon le créer
            cursor.execute("SELECT id_player FROM players WHERE pseudo = %s", (player_name,))
            result = cursor.fetchone()
            if result is None:
                cursor.execute("INSERT INTO players (pseudo) VALUES (%s) RETURNING id_player", (player_name,))
                id_player = cursor.fetchone()['id_player']
            else:
                id_player = result['id_player']
                
            # Déterminer le rôle (pour simplifier, utilisons le rôle préféré)
            role_name = 'villager' if role_preference == 'villageois' else 'werewolf'
            cursor.execute("SELECT id_role FROM roles WHERE role_name = %s", (role_name,))
            id_role = cursor.fetchone()['id_role']
            
            # Inscrire le joueur à la partie
            cursor.execute("INSERT INTO players_in_parties (id_party, id_player, id_role) VALUES (%s, %s, %s)",
                          (id_party, id_player, id_role))
            conn.commit()
            
            response = {
                "status": "OK",
                "id_party": id_party,
                "id_player": id_player
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler, port=8080):
    server_address = ('0.0.0.0', port)  # Accepte les connexions de toutes les interfaces
    httpd = server_class(server_address, handler_class)
    print(f"Starting httpd server on port {port}")
    httpd.serve_forever()
    
if __name__ == "__main__":
    run()