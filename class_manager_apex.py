import json
import os
import webbrowser
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, simpledialog, Toplevel, scrolledtext
from urllib.parse import quote
import subprocess
import qrcode
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from urllib.parse import urlparse, parse_qs
from pyngrok import ngrok

# Variabile globale per il lock
checkin_lock = threading.Lock()
# Variabile globale per l'URL pubblico di ngrok
public_url = None

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
        messagebox.showerror("Errore GitHub", error_message)
    except FileNotFoundError:
        messagebox.showerror("Errore Git", "Errore: Git non è stato trovato. Assicurati che sia installato e configurato correttamente.")
    except subprocess.TimeoutExpired:
        messagebox.showerror("Errore Git", "Errore: L'operazione Git è andata in timeout. Prova a verificare la tua connessione internet o le dimensioni del repository.")
    except Exception as e:
        messagebox.showerror("Errore Inaspettato", f"Si è verificato un errore inaspettato durante il caricamento su GitHub: {e}")
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
            # Controllo per evitare sovrascritture accidentali
            if nuovo_nome_std in self.dati_collaboratori and nuovo_nome_std != nome_attuale_std:
                return False, f"Errore: Il nome '{nuovo_nome_std}' esiste già."
            
            self.dati_collaboratori[nuovo_nome_std] = self.dati_collaboratori.pop(nome_attuale_std)
            self.salva_dati()
            self.salva_cronologia()
            self.genera_report_html_e_carica()
            return True, f"Nome '{nome_attuale_std}' modificato in '{nuovo_nome_std}'."
        return False, f"Errore: Il collaboratore '{nome_attuale_std}' non esiste."
        
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
                messagebox.showerror("Errore Caricamento", f"Errore: Il file '{self.filename}' è corrotto. Tentativo di ripristino automatico dall'ultimo backup...")
                
        if not caricato_con_successo:
            ultimo_backup = self.trova_ultimo_backup()
            if ultimo_backup:
                try:
                    with open(ultimo_backup, 'r') as f:
                        self.dati_collaboratori = json.load(f)
                    
                    # Sovrascrivi il file principale con i dati del backup
                    self.salva_dati()
                    messagebox.showinfo("Ripristino", f"Ripristino automatico riuscito!\nI dati sono stati recuperati da:\n'{os.path.basename(ultimo_backup)}'")
                except (json.JSONDecodeError, FileNotFoundError):
                    messagebox.showerror("Errore Ripristino", "Errore: Impossibile caricare il backup. La classifica verrà inizializzata vuota.")
                    self.dati_collaboratori = {}
            else:
                messagebox.showinfo("Avviso", "Nessun backup trovato. La classifica verrà inizializzata vuota.")
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
        
        *** MODIFICATO PER GESTIRE LA DUPLICAZIONE DEI PUNTI MEETING DAY ***
        """
        # Acquisisci il lock per evitare race condition durante la scrittura
        checkin_lock.acquire()
        try:
            punti_da_aggiungere = self.punti_azioni.get(azione, 0)
            
            if punti_da_aggiungere == 0:
                return f"Errore: Azione '{azione}' non riconosciuta."
            
            # Se l'azione è "Meeting day", controlla se è già stata registrata oggi
            if azione == 'Meeting day':
                oggi_str = datetime.now().strftime("%Y-%m-%d")
                if nome_collaboratore_standardizzato in self.dati_collaboratori:
                    for entry in self.dati_collaboratori[nome_collaboratore_standardizzato]:
                        if entry['azione'] == 'Meeting day' and entry['data'].startswith(oggi_str):
                            # Trovata una voce, non aggiungere e restituisci errore
                            return f"Errore: {nome_collaboratore_standardizzato} ha già effettuato il check-in per il Meeting day di oggi."

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
        finally:
            # Rilascia il lock
            checkin_lock.release()
        
    def elimina_riga(self, nome_collaboratore, indice_riga):
        """
        Elimina una riga specifica dall'elenco delle azioni di un collaboratore.
        L'indice della riga parte da 0.
        """
        nome = self.standardizza_nome(nome_collaboratore)
        
        if nome not in self.dati_collaboratori:
            return False, f"Errore: Il collaboratore '{nome}' non esiste."
        
        if not (0 <= indice_riga < len(self.dati_collaboratori[nome])):
            return False, f"Errore: L'indice di riga {indice_riga + 1} non è valido per il collaboratore '{nome}'."

        azione_rimossa = self.dati_collaboratori[nome].pop(indice_riga)
        self.salva_dati()
        self.salva_cronologia()
        self.genera_report_html_e_carica()
        
        return True, f"Rimossa l'azione '{azione_rimossa['azione']}' del collaboratore {nome} (rimossi {azione_rimossa['punti']} punti)."
        
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
            return True, f"Collaboratore '{nome}' eliminato con successo."
        else:
            return False, f"Errore: Il collaboratore '{nome}' non esiste."
        
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

        # Legenda dei punti come lista di elementi HTML
        leggenda_punti_html = """
        <div class="leggenda">
            <h2>Regole Punti</h2>
            <ul>
                <li>Collaboratore diretto iscritt: 100pt ✔</li>
                <li>Partecipazione ai meeting: 50pt ✔</li>
                <li>Partecipazione ai cyl: 50pt ✔</li>
                <li>Incentive da 5 contratti: 50 pt✔</li>
                <li>Ospite seduti a step one: 25 pt ✔</li>
            </ul>
        </div>
        """
        
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
                <link rel="manifest" href="manifest.json">
                <link rel="apple-touch-icon" href="logo_512.png">
                <style>
                    body {{ font-family: sans-serif; text-align: center; margin-top: 50px; }}
                </style>
            </head>
            <body>
                <img src="logo_ubroker.png" alt="Logo Ubroker" style="max-width: 200px; margin-bottom: 20px;">
                <h1 style="color: {colore_primario};">CLASSIFICA APEX CHALLENGE</h1>
                <h2>La classifica è vuota. Inserisci dei dati per generare il report.</h2>
                {leggenda_punti_html}
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
                <link rel="manifest" href="manifest.json">
                <link rel="apple-touch-icon" href="logo_512.png">
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
                    .leggenda {{
                        margin-top: 50px;
                        text-align: left;
                        border: 1px solid #ccc;
                        padding: 20px;
                        border-radius: 10px;
                        background-color: #f9f9f9;
                    }}
                    .leggenda h2 {{
                        color: {colore_primario};
                        border-bottom: 2px solid {colore_secondario};
                        padding-bottom: 5px;
                    }}
                    .leggenda ul {{
                        list-style-type: none;
                        padding-left: 0;
                    }}
                    .leggenda li {{
                        margin-bottom: 10px;
                        font-weight: 500;
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
            
            html_content += f"""
                    </div>
                    {leggenda_punti_html}
                </div>
                <script>
                    // Imposta la data e l'ora di chiusura del contest (23 ottobre 2025)
                    var countDownDate = new Date("Oct 23, 2025 23:59:59").getTime();

                    // Aggiorna il countdown ogni 1 secondo
                    var x = setInterval(function() {{
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
                        if (distance < 0) {{
                            clearInterval(x);
                            document.getElementById("countdown-timer").innerHTML = "Il contest è terminato!";
                        }}
                    }}, 1000);
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
    
# --- Gestione server web e QR code ---
class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global classifica_manager
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_components = parse_qs(parsed_path.query)

        if path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            try:
                with open('checkin.html', 'r') as file:
                    self.wfile.write(file.read().encode())
            except FileNotFoundError:
                messagebox.showerror("Errore", "File 'checkin.html' non trovato. Assicurati che sia nella stessa cartella dell'applicazione.")
                self.wfile.write(b"Errore: File 'checkin.html' non trovato.")
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
                
                if "Errore" in messaggio:
                    titolo = "Attenzione!"
                    colore = "#ff6f00"
                else:
                    titolo = "Check-in Completato!"
                    colore = "#0d47a1"
                
                risposta_finale_html = f"""
                <!DOCTYPE html>
                <html lang="it">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>{titolo}</title>
                    <style>
                        body {{ font-family: sans-serif; text-align: center; margin-top: 50px; }}
                        h1 {{ color: {colore}; }}
                        p {{ font-size: 1.2em; }}
                    </style>
                </head>
                <body>
                    <h1>{titolo}</h1>
                    <p>{messaggio}</p>
                </body>
                </html>
                """
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(risposta_finale_html.encode('utf-8'))
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Errore: Nome non fornito per l'esecuzione del check-in.")
        elif path == '/logo_ubroker.png':
            try:
                self.send_response(200)
                self.send_header('Content-type', 'image/png')
                self.end_headers()
                with open('logo_ubroker.png', 'rb') as file:
                    self.wfile.write(file.read())
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"File non trovato.")
        elif path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Pagina non trovata.")

# --- Avvio del server in un thread separato ---
class ServerThread(threading.Thread):
    def __init__(self, port, server_class=HTTPServer, handler_class=MyHandler):
        threading.Thread.__init__(self)
        self.port = port
        self.server_class = server_class
        self.handler_class = handler_class
        self.httpd = None
        self.is_running = False

    def run(self):
        try:
            self.server_address = ('', self.port)
            self.httpd = self.server_class(self.server_address, self.handler_class)
            self.is_running = True
            print(f"Server avviato sulla porta {self.port}...")
            self.httpd.serve_forever()
        except Exception as e:
            print(f"Errore durante l'avvio del server: {e}")
        finally:
            self.is_running = False

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            print("Server arrestato.")

# --- Nuova funzione per la gestione della classifica (spostata qui) ---
def mostra_gestione_classifica():
    global classifica_manager, window
    gestione_window = Toplevel(window)
    gestione_window.title("Gestione Collaboratori e Punti")
    gestione_window.geometry("600x650")

    frame_gestione = tk.Frame(gestione_window, padx=10, pady=10)
    frame_gestione.pack(fill="both", expand=True)

    tk.Label(frame_gestione, text="Seleziona un collaboratore:", font=("Helvetica", 10, "bold")).pack(pady=(0, 5))
    
    # Listbox per mostrare i collaboratori
    listbox_collaboratori = tk.Listbox(frame_gestione, height=15)
    listbox_collaboratori.pack(fill="x", expand=False, pady=(0, 10))
    
    # Funzione per popolare la Listbox
    def popola_listbox():
        listbox_collaboratori.delete(0, tk.END)
        for nome_collaboratore in sorted(classifica_manager.dati_collaboratori.keys()):
            punteggio = classifica_manager.calcola_punteggio_totale(nome_collaboratore)
            listbox_collaboratori.insert(tk.END, f"{nome_collaboratore} ({punteggio} punti)")
            
    popola_listbox()

    # Funzione per gestire i pulsanti di modifica/eliminazione
    def seleziona_collaboratore():
        try:
            indice = listbox_collaboratori.curselection()[0]
            nome_selezionato_completo = listbox_collaboratori.get(indice)
            nome_selezionato = nome_selezionato_completo.split(" (")[0]
            
            # Finestra di dialogo per la modifica/eliminazione
            modifica_window = Toplevel(gestione_window)
            modifica_window.title(f"Gestisci: {nome_selezionato}")
            modifica_window.geometry("450x550")

            frame_modifica = tk.Frame(modifica_window, padx=10, pady=10)
            frame_modifica.pack(fill="both", expand=True)

            # Sezione per modificare il nome
            tk.Label(frame_modifica, text="Modifica Nome Collaboratore:", font=("Helvetica", 10, "bold")).pack(pady=(0, 5))
            entry_modifica_nome = tk.Entry(frame_modifica, width=50)
            entry_modifica_nome.insert(0, nome_selezionato)
            entry_modifica_nome.pack(pady=(0, 5))

            def esegui_modifica_nome():
                nuovo_nome = entry_modifica_nome.get()
                if nuovo_nome and nuovo_nome != nome_selezionato:
                    successo, messaggio = classifica_manager.modifica_nome_collaboratore(nome_selezionato, nuovo_nome)
                    if successo:
                        messagebox.showinfo("Successo", messaggio)
                        popola_listbox() # Aggiorna la lista
                        modifica_window.destroy()
                    else:
                        messagebox.showerror("Errore", messaggio)
                else:
                    messagebox.showinfo("Avviso", "Nessuna modifica del nome.")

            tk.Button(frame_modifica, text="Salva Nuovo Nome", command=esegui_modifica_nome).pack(pady=5)
            
            tk.Frame(frame_modifica, height=2, bg="gray").pack(fill="x", pady=10)

            # Sezione per eliminare il collaboratore
            tk.Label(frame_modifica, text="Elimina Collaboratore:", font=("Helvetica", 10, "bold")).pack(pady=(0, 5))
            def esegui_eliminazione_collaboratore():
                if messagebox.askyesno("Conferma", f"Sei sicuro di voler eliminare definitivamente il collaboratore '{nome_selezionato}' e tutti i suoi dati?"):
                    successo, messaggio = classifica_manager.elimina_collaboratore(nome_selezionato)
                    if successo:
                        messagebox.showinfo("Successo", messaggio)
                        popola_listbox() # Aggiorna la lista
                        modifica_window.destroy()
                    else:
                        messagebox.showerror("Errore", messaggio)
            tk.Button(frame_modifica, text="Elimina Collaboratore", fg="red", command=esegui_eliminazione_collaboratore).pack(pady=5)
            
            tk.Frame(frame_modifica, height=2, bg="gray").pack(fill="x", pady=10)

            # Sezione per eliminare singole azioni
            tk.Label(frame_modifica, text="Azioni Registrate:", font=("Helvetica", 10, "bold")).pack(pady=(0, 5))
            
            # Listbox per mostrare i dettagli delle azioni
            listbox_azioni = scrolledtext.ScrolledText(frame_modifica, width=50, height=10)
            listbox_azioni.pack(fill="both", expand=True)
            
            def aggiorna_dettagli_azioni():
                listbox_azioni.config(state=tk.NORMAL)
                listbox_azioni.delete("1.0", tk.END)
                dettagli_collaboratore_aggiornati = classifica_manager.mostra_dettaglio_classifica(nome_selezionato)
                listbox_azioni.insert(tk.INSERT, "\n".join(dettagli_collaboratore_aggiornati))
                listbox_azioni.config(state=tk.DISABLED)

            aggiorna_dettagli_azioni()

            def esegui_eliminazione_punti():
                indice_riga_input = simpledialog.askinteger("Elimina Punti", "Inserisci il numero di riga (es. 1, 2, 3...) da eliminare:", parent=modifica_window)
                if indice_riga_input is not None:
                    # L'utente ha inserito un numero
                    indice_riga = int(indice_riga_input) - 1 # Converti l'indice per la lista Python
                    if indice_riga >= 0:
                        successo, messaggio = classifica_manager.elimina_riga(nome_selezionato, indice_riga)
                        if successo:
                            messagebox.showinfo("Successo", messaggio)
                            # Aggiorna le listbox dopo l'eliminazione
                            popola_listbox() 
                            aggiorna_dettagli_azioni()
                        else:
                            messagebox.showerror("Errore", messaggio)
                    else:
                        messagebox.showerror("Errore", "Indice non valido. Deve essere un numero maggiore di 0.")
            
            tk.Button(frame_modifica, text="Elimina Punti per Riga", command=esegui_eliminazione_punti).pack(pady=5)

        except IndexError:
            messagebox.showerror("Errore", "Seleziona un collaboratore dalla lista.")

    tk.Button(frame_gestione, text="Gestisci Collaboratore Selezionato", command=seleziona_collaboratore).pack(pady=10)

# --- Interfaccia principale (PySimpleGUI rimosso) ---
def main():
    global classifica_manager
    global public_url
    global window
    classifica_manager = ClassificaManager()
    
    server_port = 8000
    server_thread = ServerThread(server_port)
    server_thread.daemon = True
    server_thread.start()

    # Creazione della finestra principale di Tkinter
    window = tk.Tk()
    window.title("Apex Challenge Report")
    window.geometry("700x550") # Aumento le dimensioni per la nuova finestra
    
    # Crea un menu a tendina
    menubar = tk.Menu(window)
    window.config(menu=menubar)

    # Menu Opzioni
    opzioni_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Opzioni", menu=opzioni_menu)
    opzioni_menu.add_command(label="Gestione Classifica", command=mostra_gestione_classifica)
    opzioni_menu.add_separator()
    opzioni_menu.add_command(label="Esci", command=window.quit)

    # Funzione per gestire l'avvio e la chiusura di ngrok
    def gestisci_ngrok(action):
        global public_url
        if action == "start":
            if public_url:
                messagebox.showinfo("ngrok", f"ngrok è già in esecuzione: {public_url}")
                return
            try:
                tunnel = ngrok.connect(server_port)
                public_url = tunnel.public_url
                # L'URL per il QR code dovrebbe puntare al server web locale
                qrcode_url = f"{public_url}/?nome=nome_collaboratore" 
                qrcode_img = qrcode.make(qrcode_url)
                qrcode_img.save("qrcode.png")
                messagebox.showinfo("ngrok Avviato", f"ngrok è stato avviato con successo. URL: {public_url}")
            except Exception as e:
                messagebox.showerror("Errore ngrok", f"Errore durante l'avvio di ngrok: {e}")
        elif action == "stop":
            if not public_url:
                messagebox.showinfo("ngrok", "ngrok non è in esecuzione.")
                return
            try:
                ngrok.kill()
                public_url = None
                if os.path.exists("qrcode.png"):
                    os.remove("qrcode.png")
                messagebox.showinfo("ngrok Arrestato", "ngrok è stato arrestato con successo.")
            except Exception as e:
                messagebox.showerror("Errore ngrok", f"Errore durante l'arresto di ngrok: {e}")
    
    # Layout a 3 colonne per i pulsanti principali
    main_frame = tk.Frame(window, padx=20, pady=20)
    main_frame.pack(expand=True, fill='both')

    # Sezione "Gestione Collaboratori"
    collaboratori_frame = tk.LabelFrame(main_frame, text="Gestione Collaboratori", padx=10, pady=10)
    collaboratori_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    tk.Label(collaboratori_frame, text="Nome:", anchor="w").pack(fill='x', pady=(0, 2))
    entry_collaboratore = tk.Entry(collaboratori_frame)
    entry_collaboratore.pack(fill='x', pady=(0, 5))

    def aggiungi_collaboratore_gui():
        nome = entry_collaboratore.get()
        if nome:
            nome_std = classifica_manager.standardizza_nome(nome)
            if nome_std not in classifica_manager.dati_collaboratori:
                classifica_manager.dati_collaboratori[nome_std] = []
                classifica_manager.salva_dati()
                classifica_manager.salva_cronologia()
                classifica_manager.genera_report_html_e_carica()
                messagebox.showinfo("Successo", f"Collaboratore '{nome_std}' aggiunto.")
            else:
                messagebox.showerror("Errore", "Collaboratore già esistente.")
    
    tk.Button(collaboratori_frame, text="Aggiungi Collaboratore", command=aggiungi_collaboratore_gui).pack(fill='x', pady=2)


    # Sezione "Gestione Punti"
    punti_frame = tk.LabelFrame(main_frame, text="Gestione Punti", padx=10, pady=10)
    punti_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

    tk.Label(punti_frame, text="Collaboratore:", anchor="w").pack(fill='x', pady=(0, 2))
    entry_collaboratore_punti = tk.Entry(punti_frame)
    entry_collaboratore_punti.pack(fill='x', pady=(0, 5))
    
    tk.Label(punti_frame, text="Azione:", anchor="w").pack(fill='x', pady=(0, 2))
    opzioni_azioni = list(classifica_manager.punti_azioni.keys())
    variabile_azione = tk.StringVar(punti_frame)
    variabile_azione.set(opzioni_azioni[0])
    menu_azioni = tk.OptionMenu(punti_frame, variabile_azione, *opzioni_azioni)
    menu_azioni.pack(fill='x', pady=(0, 5))
    
    def aggiungi_punti_gui():
        nome_input = entry_collaboratore_punti.get()
        azione = variabile_azione.get()
        nome_std = classifica_manager.cerca_collaboratore_flessibile(nome_input)
        if nome_std:
            risultato = classifica_manager.aggiungi_azione(nome_std, azione)
            messagebox.showinfo("Risultato", risultato)
        else:
            messagebox.showerror("Errore", f"Collaboratore '{nome_input}' non trovato.")
    
    tk.Button(punti_frame, text="Aggiungi Punti", command=aggiungi_punti_gui).pack(fill='x', pady=2)

    # Sezione "Report Online"
    report_frame = tk.LabelFrame(main_frame, text="Report e Gestione Online", padx=10, pady=10)
    report_frame.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")

    def apri_report_locale():
        classifica_manager.genera_report_html()
        report_path = os.path.abspath("index.html")
        webbrowser.open(f"file://{report_path}")
    tk.Button(report_frame, text="Apri Report Locale", command=apri_report_locale).pack(fill='x', pady=2)

    def carica_e_aggiorna():
        if carica_su_github():
            messagebox.showinfo("Successo", "Report HTML generato e caricato su GitHub con successo!")
        else:
            messagebox.showerror("Errore", "Caricamento su GitHub fallito.")
    tk.Button(report_frame, text="Carica e Aggiorna su GitHub", command=carica_e_aggiorna).pack(fill='x', pady=2)

    tk.Button(report_frame, text="Avvia Server Web (ngrok)", command=lambda: gestisci_ngrok("start")).pack(fill='x', pady=2)
    tk.Button(report_frame, text="Ferma Server Web (ngrok)", command=lambda: gestisci_ngrok("stop")).pack(fill='x', pady=2)
    tk.Button(report_frame, text="Mostra QR Code", command=lambda: os.startfile("qrcode.png") if os.path.exists("qrcode.png") else messagebox.showinfo("Avviso", "QR code non generato. Avvia ngrok prima.")).pack(fill='x', pady=2)
    
    # Configura le colonne per essere ridimensionabili
    main_frame.grid_columnconfigure(0, weight=1)
    main_frame.grid_columnconfigure(1, weight=1)
    main_frame.grid_columnconfigure(2, weight=1)

    # Funzione per gestire la chiusura dell'applicazione
    def on_closing():
        if server_thread and server_thread.is_running:
            server_thread.stop()
        if public_url:
            ngrok.kill()
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", on_closing)
    window.mainloop()

if __name__ == "__main__":
    main()