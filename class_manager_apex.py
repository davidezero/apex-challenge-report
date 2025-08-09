import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
import webbrowser
import threading
import time

URL_REPORT_ONLINE = "https://davidezero.github.io/apex-challenge-report/"


class ClassManagerApex:
    def __init__(self):
        self.filename = 'classifica_apex_data.json'
        self.data = self.load_data()
        self.html_filename = 'index.html'

    def load_data(self):
        if not os.path.exists(self.filename):
            return {"collaborators": {}}
        with open(self.filename, 'r') as file:
            return json.load(file)

    def save_data(self):
        with open(self.filename, 'w') as file:
            json.dump(self.data, file, indent=4)

    def add_collaborator(self, name):
        if name not in self.data["collaborators"]:
            self.data["collaborators"][name] = {"points": 0, "actions": []}
            print(f"Collaboratore {name} aggiunto.")
        else:
            print(f"Collaboratore {name} esiste già.")
        self.save_data()

    def add_action(self, name, action, points):
        if name in self.data["collaborators"]:
            self.data["collaborators"][name]["points"] += points
            self.data["collaborators"][name]["actions"].append({"action": action, "points": points, "timestamp": time.time()})
            print(f"Azione '{action}' aggiunta per {name}. Punti: {points}.")
        else:
            print(f"Collaboratore {name} non trovato.")
        self.save_data()

    def generate_html_report(self):
        sorted_collaborators = sorted(self.data["collaborators"].items(), key=lambda x: x[1]["points"], reverse=True)

        html_content = """
        <!DOCTYPE html>
        <html lang="it">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Classifica Apex Challenge</title>
            <style>
                body { font-family: Arial, sans-serif; background-color: #121212; color: #e0e0e0; margin: 0; padding: 20px; }
                .container { max-width: 800px; margin: auto; background: #1e1e1e; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0, 0, 0, 0.5); }
                h1, h2 { color: #bb86fc; text-align: center; }
                table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                th, td { padding: 12px; border: 1px solid #333; text-align: left; }
                th { background-color: #3700b3; color: white; }
                tr:nth-child(even) { background-color: #2c2c2c; }
                tr:hover { background-color: #424242; }
                .logo { display: block; margin: 0 auto 20px; max-width: 150px; }
            </style>
        </head>
        <body>
            <div class="container">
                <img src="logo_ubroker.png" alt="Logo Ubroker" class="logo">
                <h1>Classifica Apex Challenge</h1>
                <table>
                    <thead>
                        <tr>
                            <th>Nome</th>
                            <th>Punti</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        for name, info in sorted_collaborators:
            html_content += f"<tr><td>{name}</td><td>{info['points']}</td></tr>"

        html_content += """
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """
        with open(self.html_filename, 'w') as file:
            file.write(html_content)

    def serve_report(self):
        os.chdir(os.path.dirname(os.path.abspath(_file_)))
        try:
            httpd = HTTPServer(('localhost', 8000), SimpleHTTPRequestHandler)
            print("Server avviato su http://localhost:8000")
            threading.Thread(target=httpd.serve_forever).start()
            webbrowser.open_new_tab('http://localhost:8000/index.html')
        except Exception as e:
            print(f"Errore nell'avvio del server: {e}")

    def main_menu(self):
        while True:
            self.generate_html_report()
            print("\n--- Menù Apex Challenge ---")
            print("1. Aggiungi collaboratore")
            print("2. Aggiungi azione a collaboratore")
            print("3. Visualizza report HTML (sul browser)")
            print("4. Apri report online")
            print("5. Carica modifiche su GitHub")
            print("0. Esci")

            choice = input("Scegli un'opzione: ")

            if choice == '1':
                name = input("Inserisci il nome del nuovo collaboratore: ")
                self.add_collaborator(name)
            elif choice == '2':
                name = input("Inserisci il nome del collaboratore: ")
                action = input("Inserisci la descrizione dell'azione: ")
                points = int(input("Inserisci i punti da aggiungere: "))
                self.add_action(name, action, points)
            elif choice == '3':
                self.serve_report()
            elif choice == '4':
                webbrowser.open_new_tab(URL_REPORT_ONLINE)
            elif choice == '5':
                os.system('git add .')
                os.system('git commit -m "Aggiornamento classifica"')
                os.system('git push')
            elif choice == '0':
                break
            else:
                print("Opzione non valida. Riprova.")

if __name__ == "__main__":
    app = ClassManagerApex()
    app.main_menu()