from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import psycopg2

# Connexion à la base de données
conn = psycopg2.connect(
    dbname="wolf_game",
    user="wolf_admin",
    password="motdepasse_secure",
    host="db",
    port="5432"
)
cursor = conn.cursor()

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/list_parties':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            # Récupérer les parties depuis la base de données
            cursor.execute("SELECT id_party, title_party FROM parties WHERE is_started = FALSE AND is_finished = FALSE")
            parties = cursor.fetchall()
            parties_data = {"id_parties": [party[0] for party in parties]}

            self.wfile.write(json.dumps(parties_data).encode('utf-8'))
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
            self.end_headers()

            # Logique pour s'inscrire à une partie
            player = data["player"]
            id_party = data["id_party"]

            # Vérifier si le joueur existe, sinon le créer
            cursor.execute("SELECT id_player FROM players WHERE pseudo = %s", (player,))
            result = cursor.fetchone()
            if result is None:
                cursor.execute("INSERT INTO players (pseudo) VALUES (%s) RETURNING id_player", (player,))
                id_player = cursor.fetchone()[0]
            else:
                id_player = result[0]

            # Inscrire le joueur à la partie
            cursor.execute("INSERT INTO players_in_parties (id_party, id_player, id_role) VALUES (%s, %s, (SELECT id_role FROM roles WHERE role_name = 'villager' LIMIT 1))", (id_party, id_player))
            conn.commit()

            response = {
                "status": "OK",
                "response": {
                    "role": "villager",
                    "id_player": id_player
                }
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Starting httpd server on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
