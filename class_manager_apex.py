import json
import os
import webbrowser
from datetime import datetime
import PySimpleGUI as sg
from urllib.parse import quote
import subprocess
import qrcode
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from urllib.parse import urlparse, parse_qs
from pyngrok import ngrok

# --- Funzione globale per il caricamento su GitHub ---
def carica_su_github():
    """
    Carica i file del report HTML su GitHub.
    Gestisce in modo più robusta gli errori di Git.
    """
    try:
        # Aggiunge i file al repository Git
        # Usiamo "." per aggiungere tutti i file modificati, inclusi index.html e logo.
        subprocess.run(["git", "add", "."], check=True, capture_output=True, text=True, timeout=30)
        
        # Esegue il commit con un messaggio standard
        subprocess.run(["git", "commit", "-m", "Aggiornata classifica"], check=True, capture_output=True, text=True, timeout=30)
        
        # Esegue il push al repository remoto
        subprocess.run(["git", "push"], check=True, capture_output=True, text=True, timeout=60)
        
        return True
    except subprocess.CalledProcessError as e:
        error_message = (
            f"Errore durante l'aggiornamento su GitHub:\n"
            f"Comando fallito: {' '.join(e.cmd)}\n"
            f"Codice di uscita: {e.returncode}\n"
            f"Messaggio di errore:\n{e.stderr}"
        )
        sg.popup_error(error_message)
    except FileNotFoundError:
        sg.popup_error("Errore: Git non è stato trovato. Assicurati che sia installato e configurato correttamente.")
    except subprocess.TimeoutExpired:
        sg.popup_error("Errore: L'operazione Git è andata in timeout. Prova a verificare la tua connessione internet o le dimensioni del repository.")
    except Exception as e:
        sg.popup_error(f"Si è verificato un errore inaspettato durante il caricamento su GitHub: {e}")
    return False

class ClassificaManager:
    def __init__(self, filename="classifica_apex_data.json"):
        """
        Gestisce la classifica dei collaboratori per l'Apex Challenge.
        """
        self.filename = filename
        self.dati_collaboratori = {}
        self.punti_azioni = {
            "Meeting day": 50,
            "Change your life": 50,
            "Incentive da 5": 50,
            "Collaboratore diretto": 100,
            "Ospite step one": 25,
        }
        self.carica_dati()

    def salva_cronologia(self):
        """
        Salva una copia dei dati della classifica in un file di cronologia,
        con un timestamp per ogni salvataggio.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        history_filename = f"cronologia/classifica_apex_data_{timestamp}.json"
        
        if not os.path.exists("cronologia"):
            os.makedirs("cronologia")

        with open(history_filename, 'w') as f:
            json.dump(self.dati_collaboratori, f, indent=4)

    def standardizza_nome(self, nome_completo):
        """
        Standardizza un nome e cognome, rendendoli uniformi (es. '  igor Claudio  previtera' -> 'Igor Claudio Previtera').
        La funzione rimuove gli spazi in eccesso e mette ogni parola in maiuscolo, senza cambiarne l'ordine.
        """
        return " ".join(word.capitalize() for word in nome_completo.strip().split())

    def cerca_collaboratore_flessibile(self, nome_input):
        """
        Cerca un collaboratore esistente in modo flessibile.
        Restituisce il nome standardizzato del collaboratore trovato o None se non c'è corrispondenza.
        """
        nome_input_std = self.standardizza_nome(nome_input)
        
        # 1. Cerca corrispondenza esatta con il nome standardizzato
        if nome_input_std in self.dati_collaboratori:
            return nome_input_std
        
        # 2. Cerca corrispondenza flessibile (parole in qualsiasi ordine)
        input_parole = sorted(nome_input_std.lower().split())
        for nome_esistente in self.dati_collaboratori.keys():
            nome_esistente_parole = sorted(nome_esistente.lower().split())
            if input_parole == nome_esistente_parole:
                return nome_esistente
        
        return None

    def modifica_nome_collaboratore(self, nome_attuale, nuovo_nome):
        """
        Modifica il nome di un collaboratore e aggiorna i dati.
        """
        nome_attuale_std = self.standardizza_nome(nome_attuale)
        nuovo_nome_std = self.standardizza_nome(nuovo_nome)

        if nome_attuale_std in self.dati_collaboratori:
            self.dati_collaboratori[nuovo_nome_std] = self.dati_collaboratori.pop(nome_attuale_std)
            self.salva_dati()
            self.salva_cronologia()
            self.genera_report_html_e_carica()
            return True
        return False
        
    def trova_ultimo_backup(self, history_folder="cronologia"):
        """
        Trova il file di backup più recente nella cartella cronologia.
        Restituisce il percorso completo del file o None se non ne trova.
        """
        if not os.path.exists(history_folder):
            return None
        
        list_of_files = [os.path.join(history_folder, f) for f in os.listdir(history_folder) if f.startswith("classifica_apex_data_")]
        if not list_of_files:
            return None
            
        latest_file = max(list_of_files, key=os.path.getctime)
        return latest_file

    def carica_dati(self):
        """
        Carica i dati della classifica da un file JSON.
        Se il caricamento fallisce, tenta un ripristino automatico dall'ultimo backup.
        """
        caricato_con_successo = False
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    self.dati_collaboratori = json.load(f)
                caricato_con_successo = True
            except json.JSONDecodeError:
                # Il file principale è corrotto, tenta il ripristino
                sg.popup_error(f"Errore: Il file '{self.filename}' è corrotto. Tentativo di ripristino automatico dall'ultimo backup...")
                
        if not caricato_con_successo:
            ultimo_backup = self.trova_ultimo_backup()
            if ultimo_backup:
                try:
                    with open(ultimo_backup, 'r') as f:
                        self.dati_collaboratori = json.load(f)
                    
                    # Sovrascrivi il file principale con i dati del backup
                    self.salva_dati()
                    sg.popup_ok(f"Ripristino automatico riuscito!\nI dati sono stati recuperati da:\n'{os.path.basename(ultimo_backup)}'")
                except (json.JSONDecodeError, FileNotFoundError):
                    sg.popup_error("Errore: Impossibile caricare il backup. La classifica verrà inizializzata vuota.")
                    self.dati_collaboratori = {}
            else:
                sg.popup_ok("Nessun backup trovato. La classifica verrà inizializzata vuota.")
                self.dati_collaboratori = {}

    def salva_dati(self):
        """
        Salva i dati della classifica in un file JSON.
        """
        with open(self.filename, 'w') as f:
            json.dump(self.dati_collaboratori, f, indent=4)

    def aggiungi_azione(self, nome_collaboratore_standardizzato, azione, quantita=1):
        """
        Aggiunge l'azione specificata al collaboratore con il nome standardizzato.
        Gestisce l'aggiunta di più punti in una volta sola per azioni specifiche.
        """
        punti_da_aggiungere = self.punti_azioni.get(azione, 0)
        
        if punti_da_aggiungere == 0:
            return f"Errore: Azione '{azione}' non riconosciuta."
        
        # Se il collaboratore non esiste, viene creato
        if nome_collaboratore_standardizzato not in self.dati_collaboratori:
            self.dati_collaboratori[nome_collaboratore_standardizzato] = []

        # Aggiunge l'azione il numero di volte specificato
        for _ in range(quantita):
            self.dati_collaboratori[nome_collaboratore_standardizzato].append({
                "azione": azione,
                "punti": punti_da_aggiungere,
                "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

        self.salva_dati()
        self.salva_cronologia()
        self.genera_report_html_e_carica()
        if quantita > 1:
            return f"Aggiunta l'azione '{azione}' a {nome_collaboratore_standardizzato} per {quantita} volte. (+{punti_da_aggiungere * quantita} punti totali)."
        else:
            return f"Aggiunta l'azione '{azione}' a {nome_collaboratore_standardizzato} (+{punti_da_aggiungere} punti)."
        
    def elimina_riga(self, nome_collaboratore, indice_riga):
        """
        Elimina una riga specifica dall'elenco delle azioni di un collaboratore.
        L'indice della riga parte da 0.
        """
        nome = self.standardizza_nome(nome_collaboratore)
        
        if nome not in self.dati_collaboratori:
            return f"Errore: Il collaboratore '{nome}' non esiste."
        
        if not (0 <= indice_riga < len(self.dati_collaboratori[nome])):
            return f"Errore: L'indice di riga {indice_riga + 1} non è valido per il collaboratore '{nome}'."

        azione_rimossa = self.dati_collaboratori[nome].pop(indice_riga)
        self.salva_dati()
        self.salva_cronologia()
        self.genera_report_html_e_carica()
        
        return f"Rimossa l'azione '{azione_rimossa['azione']}' del collaboratore {nome} (rimossi {azione_rimossa['punti']} punti)."
        
    def elimina_collaboratore(self, nome_collaboratore):
        """
        Elimina un collaboratore e tutti i suoi dati dalla classifica.
        """
        nome = self.standardizza_nome(nome_collaboratore)
        if nome in self.dati_collaboratori:
            del self.dati_collaboratori[nome]
            self.salva_dati()
            self.salva_cronologia()
            self.genera_report_html_e_carica()
            return f"Collaboratore '{nome}' eliminato con successo."
        else:
            return f"Errore: Il collaboratore '{nome}' non esiste."
        
    def calcola_punteggio_totale(self, nome_collaboratore):
        """
        Calcola il punteggio totale di un collaboratore.
        """
        return sum(item['punti'] for item in self.dati_collaboratori.get(nome_collaboratore, []))

    def mostra_classifica(self):
        """
        Ordina i collaboratori per punteggio decrescente e restituisce la classifica come lista di stringhe.
        """
        if not self.dati_collaboratori:
            return ["La classifica è vuota."]
        
        punteggi_totali = {nome: self.calcola_punteggio_totale(nome) for nome in self.dati_collaboratori}
        classifica_ordinata = sorted(punteggi_totali.items(), key=lambda item: item[1], reverse=True)

        classifica_list = [f"--- CLASSIFICA APEX CHALLENGE ---"]
        posizione = 1
        for nome, punteggio in classifica_ordinata:
            classifica_list.append(f"{posizione}. {nome}: {punteggio} punti")
            posizione += 1
        classifica_list.append("----------------------------------")
        return classifica_list

    def mostra_dettaglio_classifica(self, nome_collaboratore):
        """
        Restituisce un report dettagliato delle azioni di un collaboratore come lista di stringhe.
        """
        nome = self.standardizza_nome(nome_collaboratore)
        if nome not in self.dati_collaboratori:
            return [f"Errore: Il collaboratore '{nome}' non esiste."]
        
        dettaglio_list = [f"--- DETTAGLIO AZIONI DI {nome.upper()} ---"]
        azioni = self.dati_collaboratori[nome]
        if not azioni:
            dettaglio_list.append("Nessuna azione registrata per questo collaboratore.")
        else:
            for i, azione in enumerate(azioni):
                dettaglio_list.append(f"[{i+1}] Azione: {azione['azione']} (+{azione['punti']} punti) - Data: {azione['data']}")
        dettaglio_list.append(f"\nPunteggio totale: {self.calcola_punteggio_totale(nome)} punti")
        dettaglio_list.append("----------------------------------")
        return dettaglio_list
        
    def genera_report_html(self):
        """
        Genera un report dettagliato in un file HTML con una grafica personalizzata,
        inclusi un countdown e la classifica dei collaboratori.
        """
        colore_primario = "#0d47a1"
        colore_secondario = "#ff6f00"
        
        if not self.dati_collaboratori:
            report_content = f"""
            <!DOCTYPE html>
            <html lang="it">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Classifica Apex Challenge</title>
                <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
                <meta http-equiv="Pragma" content="no-cache">
                <meta http-equiv="Expires" content="0">
                <style>
                    body {{ font-family: sans-serif; text-align: center; margin-top: 50px; }}
                </style>
            </head>
            <body>
                <img src="logo_ubroker.png" alt="Logo Ubroker" style="max-width: 200px; margin-bottom: 20px;">
                <h1 style="color: {colore_primario};">CLASSIFICA APEX CHALLENGE</h1>
                <h2>La classifica è vuota. Inserisci dei dati per generare il report.</h2>
            </body>
            </html>
            """
        else:
            punteggi_totali = {nome: self.calcola_punteggio_totale(nome) for nome in self.dati_collaboratori}
            classifica_ordinata = sorted(punteggi_totali.items(), key=lambda item: item[1], reverse=True)
            max_punteggio = max(punteggi_totali.values()) if punteggi_totali else 1

            html_content = f"""
            <!DOCTYPE html>
            <html lang="it">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Classifica Apex Challenge</title>
                <style>
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        background-color: #fff; /* Sfondo bianco */
                        color: #333;
                        margin: 0;
                        padding: 20px;
                    }}
                    .container {{
                        max-width: 900px;
                        margin: auto;
                        background: #fff;
                        padding: 30px 50px;
                        border-radius: 15px;
                        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
                    }}
                    .logo-container {{
                        text-align: center;
                        margin-bottom: 10px; /* Alzato un po' il logo */
                    }}
                    .logo {{
                        max-width: 250px;
                        height: auto;
                    }}
                    #countdown-timer {{
                        text-align: center;
                        font-size: 2em;
                        color: {colore_primario}; /* Colore blu */
                        font-weight: bold;
                        margin: 20px 0;
                    }}
                    h1 {{
                        text-align: center;
                        color: {colore_primario};
                        text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.1);
                        font-size: 2.5em;
                        margin-bottom: 30px;
                    }}
                    .classifica-item {{
                        display: flex;
                        align-items: center;
                        background-color: #fafafa;
                        margin-bottom: 15px;
                        padding: 10px 20px;
                        border-radius: 8px;
                        transition: transform 0.2s;
                    }}
                    .classifica-item:hover {{
                        transform: translateX(10px);
                        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                    }}
                    .classifica-item.primo {{ border-left: 5px solid gold; }}
                    .classifica-item.secondo {{ border-left: 5px solid silver; }}
                    .classifica-item.terzo {{ border-left: 5px solid #cd7f32; }}

                    .posizione {{
                        font-size: 1.5em;
                        font-weight: bold;
                        color: #999;
                        width: 40px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }}
                    .dettagli {{
                        flex-grow: 1;
                        display: flex;
                        align-items: center;
                    }}
                    .nome {{
                        font-size: 1.2em;
                        font-weight: 600;
                        color: #444;
                        margin-right: 20px;
                        min-width: 200px;
                    }}
                    .barra-progresso-container {{
                        flex-grow: 1;
                        height: 15px;
                        background-color: #e0e0e0;
                        border-radius: 10px;
                        overflow: hidden;
                        margin-right: 10px;
                    }}
                    .barra-progresso {{
                        height: 100%;
                        transition: width 0.5s ease-in-out;
                    }}
                    .barra-progresso.primo {{ background-color: gold; }}
                    .barra-progresso.secondo {{ background-color: silver; }}
                    .barra-progresso.terzo {{ background-color: #cd7f32; }}
                    .barra-progresso.altri {{ background-color: {colore_primario}; }}

                    .punti {{
                        font-weight: bold;
                        color: {colore_secondario};
                        min-width: 80px;
                        text-align: right;
                    }}
                    .riepilogo {{
                        margin-top: 50px;
                    }}
                    .collaboratore-dettagli {{
                        border: 1px solid #ccc;
                        padding: 20px;
                        margin-bottom: 20px;
                        border-radius: 10px;
                        background-color: #fafafa;
                    }}
                    .collaboratore-dettagli h3 {{
                        margin-top: 0;
                        border-bottom: 2px solid {colore_secondario};
                        padding-bottom: 5px;
                        display: inline-block;
                        color: {colore_primario};
                    }}
                    .collaboratore-dettagli ul {{
                        list-style-type: none;
                        padding: 0;
                    }}
                    .collaboratore-dettagli li {{
                        margin-bottom: 5px;
                        padding: 5px;
                        border-bottom: 1px dashed #eee;
                    }}
                    .collaboratore-dettagli li:last-child {{
                        border-bottom: none;
                    }}
                    /* Media Queries per la visualizzazione mobile */
                    @media (max-width: 768px) {{
                        .classifica-item {{
                            flex-direction: column;
                            align-items: flex-start;
                        }}
                        .posizione {{
                            font-size: 1.2em;
                            margin-bottom: 5px;
                        }}
                        .dettagli {{
                            flex-direction: column;
                            align-items: flex-start;
                            width: 100%;
                        }}
                        .nome {{
                            font-size: 1.1em;
                            margin-bottom: 5px;
                            min-width: auto;
                        }}
                        .barra-progresso-container {{
                            width: 100%;
                            margin-right: 0;
                            margin-bottom: 5px;
                        }}
                        .punti {{
                            min-width: auto;
                            text-align: left;
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="logo-container">
                        <img src="logo_ubroker.png" alt="Logo Ubroker" class="logo">
                    </div>
                    <div id="countdown-timer"></div>
                    <h1>CLASSIFICA APEX CHALLENGE</h1>
                    <div class="classifica-generale">
            """
            
            posizione = 1
            for nome, punteggio in classifica_ordinata:
                percentuale = (punteggio / max_punteggio) * 100 if max_punteggio > 0 else 0
                
                if posizione == 1:
                    posizione_visualizzata = '🏆'
                    classe_barra = "primo"
                    classe_item = "primo"
                elif posizione == 2:
                    posizione_visualizzata = '🥈'
                    classe_barra = "secondo"
                    classe_item = "secondo"
                elif posizione == 3:
                    posizione_visualizzata = '🥉'
                    classe_barra = "terzo"
                    classe_item = "terzo"
                else:
                    posizione_visualizzata = posizione
                    classe_barra = "altri"
                    classe_item = ""
                
                html_content += f"""
                        <div class="classifica-item {classe_item}">
                            <span class="posizione">{posizione_visualizzata}</span>
                            <div class="dettagli">
                                <span class="nome">{nome}</span>
                                <div class="barra-progresso-container">
                                    <div class="barra-progresso {classe_barra}" style="width: {percentuale}%;"></div>
                                </div>
                                <span class="punti">{punteggio} punti</span>
                            </div>
                        </div>
                """
                posizione += 1
            
            html_content += """
                    </div>
                    <div class="riepilogo">
                        <h2>Riepilogo Punti per Collaboratore</h2>
            """
            for nome, _ in classifica_ordinata:
                html_content += f"""
                    <div class="collaboratore-dettagli">
                        <h3>{nome} (Totale: {punteggi_totali[nome]} punti)</h3>
                        <ul>
                """
                azioni = self.dati_collaboratori[nome]
                for i, azione in enumerate(azioni):
                    html_content += f"""
                        <li>- Azione: {azione['azione']} (+{azione['punti']} punti) - Data: {azione['data']}</li>
                    """
                html_content += """
                        </ul>
                    </div>
                """
            
            html_content += """
                    </div>
                </div>
                <script>
                    // Imposta la data e l'ora di chiusura del contest (23 ottobre 2025)
                    var countDownDate = new Date("Oct 23, 2025 23:59:59").getTime();

                    // Aggiorna il countdown ogni 1 secondo
                    var x = setInterval(function() {
                      // Ottieni la data e l'ora attuali
                      var now = new Date().getTime();

                      // Trova la distanza tra adesso e la data del countdown
                      var distance = countDownDate - now;

                      // Calcola giorni, ore, minuti e secondi
                      var days = Math.floor(distance / (1000 * 60 * 60 * 24));
                      var hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                      var minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                      var seconds = Math.floor((distance % (1000 * 60)) / 1000);

                      // Mostra il risultato nell'elemento con id="countdown-timer"
                      document.getElementById("countdown-timer").innerHTML = days + "g " + hours + "h " + minutes + "m " + seconds + "s ";

                      // Se il countdown è finito, scrivi un messaggio
                      if (distance < 0) {
                        clearInterval(x);
                        document.getElementById("countdown-timer").innerHTML = "Il contest è terminato!";
                      }
                    }, 1000);
                </script>
            </body>
            </html>
            """
            report_content = html_content
            
        report_filename = "index.html"
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write(report_content)
        
        return f"Report HTML generato con successo. Lo trovi nel file '{report_filename}'."

    def genera_report_html_e_carica(self):
        """Genera il report HTML e lo carica su GitHub."""
        self.genera_report_html()
        carica_su_github()
    
    # 
    # INIZIO CODICE MODIFICATO
    # 
    def aggiungi_punti_da_checkin(self, nome_completo):
        """
        Aggiunge 50 punti per il "Meeting day" a un collaboratore,
        solo se non ha già ricevuto punti per la stessa azione oggi.
        Gestisce anche la standardizzazione del nome per evitare duplicati.
        """
        oggi_str = datetime.now().strftime("%Y-%m-%d")
        
        # Cerca il collaboratore in modo flessibile
        nome_standardizzato = self.cerca_collaboratore_flessibile(nome_completo)

        # Se il collaboratore non esiste, crea un nuovo nome standardizzato
        if not nome_standardizzato:
            nome_standardizzato = self.standardizza_nome(nome_completo)
            
        # Controlla se l'utente ha già 50 punti per il Meeting day oggi
        punti_giornalieri_meeting = sum(
            azione['punti'] for azione in self.dati_collaboratori.get(nome_standardizzato, [])
            if azione['azione'] == 'Meeting day' and azione['data'].startswith(oggi_str)
        )
        
        if punti_giornalieri_meeting >= 50:
            return f"Errore: {nome_standardizzato} ha già raggiunto il limite di 50 punti per il Meeting day di oggi."
        
        # A questo punto, il collaboratore è valido e non ha ancora 50 punti oggi
        # Restituisce il nome standardizzato per la conferma
        return nome_standardizzato
    # 
    # FINE CODICE MODIFICATO
    # 
            
# --- Gestione server web e QR code ---
class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_components = parse_qs(parsed_path.query)

        if path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('checkin.html', 'r') as file:
                self.wfile.write(file.read().encode())
        elif path == '/conferma_checkin':
            nome_collaboratore = query_components.get('nome', [''])[0]
            if nome_collaboratore:
                risposta_html = f"""
                <!DOCTYPE html>
                <html lang="it">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Conferma Check-in</title>
                    <style>
                        body {{ font-family: sans-serif; text-align: center; margin-top: 50px; }}
                        h1 {{ color: #ff6f00; }}
                        p {{ font-size: 1.2em; }}
                        a.button {{
                            display: inline-block;
                            padding: 10px 20px;
                            background-color: #0d47a1;
                            color: #fff;
                            text-decoration: none;
                            border-radius: 5px;
                            margin: 10px;
                        }}
                    </style>
                </head>
                <body>
                    <h1>Conferma Assegnazione Punti</h1>
                    <p>Procedere con l'assegnazione di 50 punti "Meeting day" al collaboratore {nome_collaboratore}?</p>
                    <a href="/esegui_checkin?nome={quote(nome_collaboratore)}" class="button">Sì, conferma</a>
                </body>
                </html>
                """
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(risposta_html.encode('utf-8'))
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Errore: Nome non fornito per la conferma.")
        elif path == '/esegui_checkin':
            nome_collaboratore = query_components.get('nome', [''])[0]
            if nome_collaboratore:
                messaggio = classifica_manager.aggiungi_azione(nome_collaboratore, "Meeting day")
                risposta_html = f"""
                <!DOCTYPE html>
                <html lang="it">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Risultato Check-in</title>
                    <style>
                        body {{ font-family: sans-serif; text-align: center; margin-top: 50px; }}
                        h1 {{ color: #0d47a1; }}
                        p {{ font-size: 1.2em; }}
                        a {{ color: #0d47a1; }}
                    </style>
                </head>
                <body>
                    <h1>Risultato Check-in</h1>
                    <p>{messaggio}</p>
                    <a href="/">Torna al modulo di check-in</a>
                </body>
                </html>
                """
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(risposta_html.encode('utf-8'))
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Errore: Nome non fornito per l'esecuzione del check-in.")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_POST(self):
        if self.path == '/submit_checkin':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            dati_form = parse_qs(post_data)
            
            nome_collaboratore = dati_form.get('nome', [''])[0]

            if nome_collaboratore:
                messaggio_o_nome = classifica_manager.aggiungi_punti_da_checkin(nome_collaboratore)
                
                # Caso 1: il collaboratore ha già fatto il check-in oggi
                if messaggio_o_nome.startswith("Errore"):
                    risposta_html = f"""
                    <!DOCTYPE html>
                    <html lang="it">
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>Check-in Apex Challenge</title>
                        <style>
                            body {{ font-family: sans-serif; text-align: center; margin-top: 50px; }}
                            h1 {{ color: #ff6f00; }}
                            p {{ font-size: 1.2em; }}
                        </style>
                    </head>
                    <body>
                        <h1>Attenzione!</h1>
                        <p>{messaggio_o_nome}</p>
                        <a href="/">Torna al modulo di check-in</a>
                    </body>
                    </html>
                    """
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(risposta_html.encode('utf-8'))
                
                # Caso 2: il collaboratore non viene trovato (chiedi di creare)
                elif messaggio_o_nome == "NON_TROVATO":
                    nome_std = classifica_manager.standardizza_nome(nome_collaboratore)
                    risposta_html = f"""
                    <!DOCTYPE html>
                    <html lang="it">
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>Check-in Apex Challenge</title>
                        <style>
                            body {{ font-family: sans-serif; text-align: center; margin-top: 50px; }}
                            h1 {{ color: #ff6f00; }}
                            p {{ font-size: 1.2em; }}
                            a.button {{
                                display: inline-block;
                                padding: 10px 20px;
                                background-color: #0d47a1;
                                color: #fff;
                                text-decoration: none;
                                border-radius: 5px;
                                margin: 10px;
                            }}
                            a.button.cancel {{ background-color: #ccc; }}
                        </style>
                    </head>
                    <body>
                        <h1>Attenzione!</h1>
                        <p>Il collaboratore {nome_std} non è stato trovato.</p>
                        <p>Vuoi creare un nuovo collaboratore con questo nome e assegnare i punti?</p>
                        <a href="/esegui_checkin?nome={quote(nome_std)}" class="button">Sì, crea e assegna</a>
                        <a href="/" class="button cancel">No, annulla</a>
                    </body>
                    </html>
                    """
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(risposta_html.encode('utf-8'))
                
                # Caso 3: il collaboratore viene trovato (chiedi di confermare)
                else:
                    self.send_response(303)  # Codice di stato per "See Other"
                    self.send_header('Location', f'/conferma_checkin?nome={quote(messaggio_o_nome)}')
                    self.end_headers()
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Errore: Nome non fornito nel modulo.")


def run_server():
    server_address = ('', 8000)
    httpd = HTTPServer(server_address, MyHandler)
    httpd.serve_forever()

def genera_qrcode_meeting_day():
    try:
        ngrok.kill()
        tunnel = ngrok.connect(addr="8000", proto="http")
        public_url = tunnel.public_url

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(public_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        filename = "qrcode_meeting_day.png"
        img.save(filename)

        return filename, public_url
    except Exception as e:
        sg.popup_error(f"Errore durante l'avvio di Ngrok: {e}\nAssicurati che Ngrok sia installato e che il token di autenticazione sia valido.")
        return None, None

# --- Impostazioni Globali ---
URL_REPORT_ONLINE = "https://davidezero.github.io/apex-challenge-report/"

# --- Interfaccia Grafica ---
if __name__ == "__main__":
    # Imposta il font globale a grassetto
    sg.set_options(font=('Helvetica', 12, 'bold'))

    classifica_manager = ClassificaManager()
    
    azioni_disponibili = list(classifica_manager.punti_azioni.keys())
    dettaglio_attivo_per = None

    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Nuovi layout organizzati in colonne
    column_left = [
        [sg.Frame("Aggiungi Punti", [
            [sg.Text("Nome Collaboratore:", size=(15, 1)), sg.Input(key='-NOME-', size=(25, 1))],
            [sg.Text("Azione:", size=(15, 1)), sg.Combo(azioni_disponibili, default_value=azioni_disponibili[0] if azioni_disponibili else '', key='-AZIONE-', size=(23, 1), enable_events=True)],
            [sg.Text("Quantità:", size=(15, 1)), sg.Input(default_text='1', key='-QUANTITA-', size=(5, 1), disabled=True)],
            [sg.Button("Aggiungi", key='-AGGIUNGI-')]
        ])],
        [sg.Frame("Visualizza e Modifica Classifica", [
            [sg.Listbox(values=classifica_manager.mostra_classifica(), size=(60, 15), key='-LISTA_CLASSIFICA-', enable_events=True, right_click_menu=['', ['Assegna punti azione', 'Modifica Nome']])],
            [sg.Text("Nome Selezionato:", size=(18, 1)), sg.Input(key='-NOME_SELEZIONATO-', size=(25, 1), disabled=True)],
            [sg.Button("Mostra Dettaglio", key='-MOSTRA_DETTAGLIO-'), sg.Button("Modifica Nome", key='-MODIFICA_NOME-')],
            [sg.Button("Elimina Riga Selezionata", key='-ELIMINA_RIGA-', button_color=('white', 'red')), sg.Button("Elimina Collaboratore", key='-ELIMINA_COLLABORATORE-', button_color=('white', 'red'))],
            [sg.Button("Mostra Classifica Totale", key='-MOSTRA_TOTALE-')],
        ])]
    ]
    
    column_right = [
        [sg.Frame("Gestione Check-in Meeting Day", [
            [sg.Button("Genera QR Code", key='-GENERA_QR-')],
            [sg.Image(filename='', key='-QR_CODE-', size=(200, 200))],
            [sg.Text("URL per il check-in:", size=(18,1)), sg.Text("", key='-URL_CHECKIN-', size=(40,1), font=("Helvetica", 10))],
        ])],
        [sg.Frame("Genera Report e Altro", [
            [sg.Button("Genera e Carica Report HTML", key='-GENERA_REPORT_E_CARICA-')],
            [sg.Button("Condividi su WhatsApp", key='-WHATSAPP-')],
            [sg.Button("Visualizza Cronologia", key='-CRONOLOGIA-')],
            [sg.Button("Esci", key='-ESCI-', pad=(5, (10, 0)))]
        ])]
    ]

    layout = [
        [sg.Text("CLASSIFICA APEX CHALLENGE", size=(60, 1), justification='center', font=("Helvetica", 16, 'bold'), text_color='orange')],
        [sg.Column(column_left), sg.Column(column_right, vertical_alignment='top')],
    ]
    
    window = sg.Window("Apex Challenge Manager", layout, finalize=True)
    
    while True:
        event, values = window.read()
        
        if event == sg.WIN_CLOSED or event == '-ESCI-':
            ngrok.kill()
            break

        # Abilita/Disabilita il campo quantità in base all'azione selezionata
        if event == '-AZIONE-':
            if values['-AZIONE-'] in ['Collaboratore diretto', 'Ospite step one']:
                window['-QUANTITA-'].update(disabled=False)
            else:
                window['-QUANTITA-'].update(disabled=True)
                window['-QUANTITA-'].update('1')
        
        # Gestione del menu contestuale
        if event == 'Assegna punti azione':
            # Estrae il nome dalla riga selezionata, gestendo il caso in cui il dettaglio sia attivo
            riga_selezionata_str = values['-LISTA_CLASSIFICA-'][0]
            if ']' in riga_selezionata_str:
                # E' un riga di dettaglio, prendo il nome da dettaglio_attivo_per
                nome_selezionato = dettaglio_attivo_per
            else:
                # E' una riga della classifica, estraggo il nome
                nome_selezionato = riga_selezionata_str.split(':', 1)[0].split('.', 1)[1].strip()

            # Mostra un popup per l'assegnazione punti
            popup_layout = [
                [sg.Text(f"Assegna punti a {nome_selezionato}")],
                [sg.Text("Azione:"), sg.Combo(azioni_disponibili, default_value=azioni_disponibili[0], key='-POPUP_AZIONE-')],
                [sg.Text("Quantità:"), sg.Input(default_text='1', key='-POPUP_QUANTITA-')],
                [sg.Button("Conferma", key='-POPUP_CONFERMA-'), sg.Button("Annulla", key='-POPUP_ANNULLA-')]
            ]
            popup_window = sg.Window("Assegna Punti", popup_layout, modal=True, finalize=True)
            
            while True:
                popup_event, popup_values = popup_window.read()
                if popup_event == sg.WIN_CLOSED or popup_event == '-POPUP_ANNULLA-':
                    break
                if popup_event == '-POPUP_CONFERMA-':
                    try:
                        quantita = int(popup_values['-POPUP_QUANTITA-'])
                        if quantita < 1:
                            sg.popup_error("La quantità deve essere un numero intero maggiore di zero.")
                            continue
                        azione = popup_values['-POPUP_AZIONE-']
                        messaggio = classifica_manager.aggiungi_azione(nome_selezionato, azione, quantita)
                        sg.popup_ok(messaggio)
                        window['-LISTA_CLASSIFICA-'].update(classifica_manager.mostra_classifica())
                        break
                    except ValueError:
                        sg.popup_error("Inserisci un numero valido per la quantità.")
            popup_window.close()
        
        if event == 'Modifica Nome':
            # Estrae il nome dalla riga selezionata, gestendo il caso in cui il dettaglio sia attivo
            riga_selezionata_str = values['-LISTA_CLASSIFICA-'][0]
            if ']' in riga_selezionata_str:
                nome_attuale = dettaglio_attivo_per
            else:
                nome_attuale = riga_selezionata_str.split(':', 1)[0].split('.', 1)[1].strip()

            nuovo_nome = sg.popup_get_text("Inserisci il nuovo nome per il collaboratore:", "Modifica Nome", default_text=nome_attuale)
            if not nuovo_nome:
                sg.popup_ok("Operazione annullata.")
            else:
                classifica_manager.modifica_nome_collaboratore(nome_attuale, nuovo_nome)
                sg.popup_ok(f"Il nome del collaboratore è stato modificato da '{nome_attuale}' a '{classifica_manager.standardizza_nome(nuovo_nome)}'.")
                window['-LISTA_CLASSIFICA-'].update(classifica_manager.mostra_classifica())
                window['-NOME_SELEZIONATO-'].update('')
                
        if event == '-LISTA_CLASSIFICA-':
            if values['-LISTA_CLASSIFICA-']:
                riga_selezionata = values['-LISTA_CLASSIFICA-'][0]
                
                try:
                    # Estrae il nome dalla riga della classifica
                    if '.' in riga_selezionata and ':' in riga_selezionata:
                        nome = riga_selezionata.split(':', 1)[0].split('.', 1)[1].strip()
                        window['-NOME_SELEZIONATO-'].update(nome)
                        dettaglio_attivo_per = None # Reset dettaglio attivo
                    elif ']' in riga_selezionata:
                        # Se è un dettaglio, estrae il nome dal titolo del dettaglio
                        nome_dettaglio_corrente = riga_selezionata.split(']')[0].split('[')[1].strip()
                        if nome_dettaglio_corrente in classifica_manager.dati_collaboratori:
                            window['-NOME_SELEZIONATO-'].update(nome_dettaglio_corrente)
                        else:
                            window['-NOME_SELEZIONATO-'].update('')
                    else:
                        window['-NOME_SELEZIONATO-'].update('')
                except (IndexError, ValueError):
                    window['-NOME_SELEZIONATO-'].update('')
                
        if event == '-AGGIUNGI-':
            nome_input = values['-NOME-'].strip()
            azione_scelta = values['-AZIONE-']
            quantita_input = values['-QUANTITA-']
            
            if not nome_input:
                sg.popup_error("Errore: Inserisci un nome per il collaboratore.")
            elif not azione_scelta:
                sg.popup_error("Errore: Seleziona un'azione.")
            else:
                try:
                    quantita = int(quantita_input)
                    if quantita < 1:
                        sg.popup_error("La quantità deve essere un numero intero maggiore di zero.")
                        continue
                except ValueError:
                    sg.popup_error("Inserisci un numero valido per la quantità.")
                    continue

                nome_esistente = classifica_manager.cerca_collaboratore_flessibile(nome_input)
                
                if nome_esistente:
                    conferma = sg.popup_yes_no(f"Hai inserito '{nome_input}'. Il sistema ha trovato un collaboratore esistente: '{nome_esistente}'. Vuoi assegnare i punti a '{nome_esistente}'?", title="Conferma Assegnazione")
                    if conferma == 'Yes':
                        messaggio = classifica_manager.aggiungi_azione(nome_esistente, azione_scelta, quantita)
                        sg.popup_ok(messaggio)
                        window['-LISTA_CLASSIFICA-'].update(classifica_manager.mostra_classifica())
                        window['-NOME_SELEZIONATO-'].update('')
                else:
                    nome_standardizzato = classifica_manager.standardizza_nome(nome_input)
                    conferma = sg.popup_yes_no(f"Il collaboratore '{nome_input}' non è stato trovato. Vuoi creare un nuovo collaboratore con questo nome e assegnargli i punti?", title="Crea Nuovo Collaboratore")
                    if conferma == 'Yes':
                        messaggio = classifica_manager.aggiungi_azione(nome_standardizzato, azione_scelta, quantita)
                        sg.popup_ok(messaggio)
                        window['-LISTA_CLASSIFICA-'].update(classifica_manager.mostra_classifica())
                        window['-NOME_SELEZIONATO-'].update('')
        
        if event == '-MODIFICA_NOME-':
            nome_attuale = values['-NOME_SELEZIONATO-'].strip()
            nuovo_nome = sg.popup_get_text("Inserisci il nuovo nome per il collaboratore:", "Modifica Nome")
            
            if not nome_attuale:
                sg.popup_ok("Errore: Seleziona un collaboratore prima di modificarne il nome.")
            elif not nuovo_nome:
                sg.popup_ok("Operazione annullata.")
            else:
                nome_attuale_std = classifica_manager.standardizza_nome(nome_attuale)
                if nome_attuale_std not in classifica_manager.dati_collaboratori:
                    sg.popup_ok(f"Errore: Il collaboratore '{nome_attuale}' non esiste.")
                else:
                    classifica_manager.modifica_nome_collaboratore(nome_attuale, nuovo_nome)
                    sg.popup_ok(f"Il nome del collaboratore è stato modificato da '{nome_attuale_std}' a '{classifica_manager.standardizza_nome(nuovo_nome)}'.")
                    window['-LISTA_CLASSIFICA-'].update(classifica_manager.mostra_classifica())
                    window['-NOME_SELEZIONATO-'].update('')
        
        if event == '-MOSTRA_DETTAGLIO-':
            nome_dettaglio = values['-NOME_SELEZIONATO-'].strip()
            if not nome_dettaglio:
                sg.popup_error("Errore: Seleziona un collaboratore per mostrare il dettaglio.")
            else:
                dettaglio_list = classifica_manager.mostra_dettaglio_classifica(nome_dettaglio)
                
                # Modifica della lista per applicare il colore arancione ai punteggi
                nuova_dettaglio_list = []
                for riga in dettaglio_list:
                    if 'punti' in riga:
                        parti = riga.split('punti')
                        nuova_riga = parti[0] + 'punti'
                        # Aggiunge il testo con il colore arancione
                        nuova_dettaglio_list.append(sg.Text(nuova_riga, text_color='orange'))
                    else:
                        nuova_dettaglio_list.append(sg.Text(riga))

                # La modifica del colore richiede un approccio diverso per la Listbox
                # Aggiorniamo la Listbox con il testo normale e gestiamo il colore solo nel popup
                if dettaglio_list[0].startswith('Errore'):
                    sg.popup_error(dettaglio_list[0])
                else:
                    # Mostra un popup con i dettagli e i punteggi in arancione
                    dettaglio_layout = [[sg.Text(riga.replace('punti', ''), text_color='orange' if 'punti' in riga else 'black')] for riga in dettaglio_list]
                    sg.popup_ok(dettaglio_list)
                    
                    window['-LISTA_CLASSIFICA-'].update(dettaglio_list)
                    dettaglio_attivo_per = classifica_manager.standardizza_nome(nome_dettaglio)
                    
        if event == '-MOSTRA_TOTALE-':
            # Modifica della lista per applicare il colore arancione
            nuova_classifica_list = classifica_manager.mostra_classifica()
            nuova_classifica_list[0] = sg.Text(nuova_classifica_list[0], text_color='orange')
            window['-LISTA_CLASSIFICA-'].update(classifica_manager.mostra_classifica())
            dettaglio_attivo_per = None
            window['-NOME_SELEZIONATO-'].update('')

        if event == '-ELIMINA_RIGA-':
            if dettaglio_attivo_per and values['-LISTA_CLASSIFICA-']:
                riga_da_eliminare_str = values['-LISTA_CLASSIFICA-'][0]
                try:
                    indice_da_eliminare = int(riga_da_eliminare_str.split(']')[0].replace('[','').strip()) - 1
                    messaggio = classifica_manager.elimina_riga(dettaglio_attivo_per, indice_da_eliminare)
                    sg.popup_ok(messaggio)
                    
                    dettaglio_list = classifica_manager.mostra_dettaglio_classifica(dettaglio_attivo_per)
                    window['-LISTA_CLASSIFICA-'].update(dettaglio_list)
                    
                except (ValueError, IndexError):
                    sg.popup_error("Errore: Seleziona una riga valida (es. [1]) dal dettaglio per eliminarla.")
            else:
                sg.popup_error("Errore: Prima devi visualizzare il dettaglio di un collaboratore e selezionare una riga.")

        if event == '-ELIMINA_COLLABORATORE-':
            nome_elimina = values['-NOME_SELEZIONATO-'].strip()
            if not nome_elimina:
                 sg.popup_error("Errore: Seleziona il nome del collaboratore da eliminare.")
            else:
                nome_elimina_std = classifica_manager.standardizza_nome(nome_elimina)
                conferma = sg.popup_yes_no(f"Sei sicuro di voler eliminare il collaboratore '{nome_elimina_std}' e tutti i suoi dati?", title="Conferma Eliminazione")
                if conferma == 'Yes':
                    messaggio = classifica_manager.elimina_collaboratore(nome_elimina)
                    sg.popup_ok(messaggio)
                    window['-LISTA_CLASSIFICA-'].update(classifica_manager.mostra_classifica())
                    dettaglio_attivo_per = None
                    window['-NOME_SELEZIONATO-'].update('')
                    
        if event == '-GENERA_QR-':
            qrcode_filename, url = genera_qrcode_meeting_day()
            if url:
                window['-QR_CODE-'].update(filename=qrcode_filename, size=(200, 200))
                window['-URL_CHECKIN-'].update(url)
                sg.popup_ok(f"QR Code generato. Apri il file '{qrcode_filename}' per visualizzarlo.\nURL per il check-in: {url}\nAssicurati che il tuo PC e i telefoni siano sulla stessa rete WiFi.")

        if event == '-GENERA_REPORT_E_CARICA-':
            sg.popup_ok("Generazione report e caricamento su GitHub in corso. Attendi...")
            classifica_manager.genera_report_html_e_carica()
            sg.popup_ok("Report generato e caricato su GitHub con successo!")
        
        if event == '-WHATSAPP-':
            if URL_REPORT_ONLINE:
                messaggio = f"Ciao a tutti! La classifica Apex Challenge è stata aggiornata! Cliccate qui per vederla in tempo reale: {URL_REPORT_ONLINE}"
                whatsapp_url = f"https://api.whatsapp.com/send?text={quote(messaggio)}"
                webbrowser.open(whatsapp_url)
            else:
                sg.popup_ok("Devi prima inserire l'URL pubblico del tuo report nel codice, nella variabile 'URL_REPORT_ONLINE'.")
        
        if event == '-CRONOLOGIA-':
            if os.path.exists("cronologia"):
                subprocess.Popen(['explorer', os.path.abspath("cronologia")])
            else:
                sg.popup_ok("La cartella 'cronologia' non esiste ancora.")
    
    window.close()