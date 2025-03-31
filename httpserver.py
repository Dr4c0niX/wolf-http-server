from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import psycopg2
import socket
import threading
import os

# Connexion à la base de données
conn = psycopg2.connect(
    dbname="wolf_game",
    user="wolf_admin",
    password="motdepasse_secure",
    host="db",
    port="5432"
)
cursor = conn.cursor()

# Stockage en mémoire des parties détaillées
party_details_cache = {}

# Configuration du serveur TCP pour les notifications
TCP_HOST = '0.0.0.0'  # Écouter sur toutes les interfaces
TCP_PORT = int(os.environ.get('HTTP_SERVER_PORT', 9000))  # Port d'écoute TCP pour les notifications

def start_tcp_server():
    """
    Démarre un serveur TCP pour recevoir les notifications de l'admin-engine
    """
    print(f"Démarrage du serveur TCP sur {TCP_HOST}:{TCP_PORT}")
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_socket:
        tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_socket.bind((TCP_HOST, TCP_PORT))
        tcp_socket.listen(5)
        
        while True:
            # Accepter les connexions
            client_socket, addr = tcp_socket.accept()
            print(f"Connexion TCP acceptée de {addr}")
            
            # Traiter la connexion dans un thread séparé
            client_thread = threading.Thread(target=handle_tcp_client, args=(client_socket,))
            client_thread.daemon = True
            client_thread.start()

def handle_tcp_client(client_socket):
    """
    Traite les messages reçus d'un client TCP
    """
    try:
        # Recevoir les données
        data = client_socket.recv(4096).decode('utf-8')
        if data:
            # Traiter le message JSON
            message = json.loads(data)
            action = message.get("action")
            
            if action == "new_party":
                party_data = message.get("data", {})
                # Mettre à jour le cache des détails de partie
                party_id = party_data.get("id_party")
                if party_id:
                    party_details_cache[str(party_id)] = party_data
                    print(f"Nouvelle partie mise en cache: {party_data}")
                    # Répondre au client
                    client_socket.sendall(json.dumps({"status": "OK", "message": "Party details cached"}).encode('utf-8'))
                else:
                    client_socket.sendall(json.dumps({"status": "ERROR", "message": "Invalid party data"}).encode('utf-8'))
            else:
                client_socket.sendall(json.dumps({"status": "ERROR", "message": "Unknown action"}).encode('utf-8'))
    except Exception as e:
        print(f"Erreur lors du traitement d'une connexion TCP: {e}")
    finally:
        client_socket.close()

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/list_parties':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            # Récupérer les parties depuis la base de données
            cursor.execute("SELECT id_party, title_party FROM parties WHERE is_started = FALSE AND is_finished = FALSE")
            parties = cursor.fetchall()
            parties_data = {
                "id_parties": [party[0] for party in parties],
                "parties_details": party_details_cache  # Ajouter les détails en cache
            }

            self.wfile.write(json.dumps(parties_data).encode('utf-8'))
        elif self.path.startswith('/party_details/'):
            party_id = self.path.split('/')[-1]
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            # Vérifier si les détails sont en cache
            if party_id in party_details_cache:
                self.wfile.write(json.dumps(party_details_cache[party_id]).encode('utf-8'))
            else:
                # Récupérer les détails de la partie depuis la base de données
                cursor.execute("SELECT id_party, title_party, grid_size, max_players, max_turns, turn_duration FROM parties WHERE id_party = %s", (party_id,))
                party = cursor.fetchone()
                if party:
                    party_info = {
                        "id_party": party[0],
                        "title": party[1],
                        "grid_size": party[2],
                        "max_players": party[3],
                        "max_turns": party[4],
                        "turn_duration": party[5],
                        "current_players": 0,
                        "villagers_count": 0,
                        "werewolves_count": 0
                    }
                    # Mettre en cache pour les futures demandes
                    party_details_cache[party_id] = party_info
                    self.wfile.write(json.dumps(party_info).encode('utf-8'))
                else:
                    self.wfile.write(json.dumps({"error": "Party not found"}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)

        if self.path == '/subscribe':
            # Code existant pour s'inscrire à une partie...
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
        elif self.path == '/create_solo_game':
            # Ajout de l'endpoint pour créer une partie solo
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            player_name = data.get("player_name")
            role_preference = data.get("role_preference")
            
            # Vérifier si le joueur existe, sinon le créer
            cursor.execute("SELECT id_player FROM players WHERE pseudo = %s", (player_name,))
            result = cursor.fetchone()
            if result is None:
                cursor.execute("INSERT INTO players (pseudo) VALUES (%s) RETURNING id_player", (player_name,))
                id_player = cursor.fetchone()[0]
            else:
                id_player = result[0]
            
            # Créer une nouvelle partie
            cursor.execute("INSERT INTO parties (title_party, is_started, is_finished) VALUES ('Solo Game', FALSE, FALSE) RETURNING id_party")
            id_party = cursor.fetchone()[0]
            
            # Inscrire le joueur à la partie
            cursor.execute("INSERT INTO players_in_parties (id_party, id_player, id_role) VALUES (%s, %s, (SELECT id_role FROM roles WHERE role_name = %s LIMIT 1))", (id_party, id_player, role_preference))
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
    # Démarrer le serveur TCP dans un thread séparé
    tcp_thread = threading.Thread(target=start_tcp_server)
    tcp_thread.daemon = True
    tcp_thread.start()
    
    # Démarrer le serveur HTTP
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Démarrage du serveur HTTP sur le port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
