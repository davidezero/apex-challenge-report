import json
import os
import webbrowser
from datetime import datetime
import PySimpleGUI as sg
from urllib.parse import quote
import subprocess  # <<<--- AGGIUNTA QUESTA LIBRERIA

class ClassificaManager:
    def __init__(self, filename="classifica_apex_data.json"):
        """
        Gestisce la classifica dei collaboratori per l'Apex Challenge.
        """
        self.filename = filename
        self.dati_collaboratori = {}
        self.punti_azioni = {
            "Change your life": 50,
            "Incentive da 5": 50,
            "Meeting day": 50,
            "Collaboratore diretto": 100,
            "Ospite step one": 25,
        }
        self.carica_dati()

    def carica_dati(self):
        """
        Carica i dati della classifica da un file JSON.
        """
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    self.dati_collaboratori = json.load(f)
            except json.JSONDecodeError:
                self.dati_collaboratori = {}

    def salva_dati(self):
        """
        Salva i dati della classifica in un file JSON.
        """
        with open(self.filename, 'w') as f:
            json.dump(self.dati_collaboratori, f, indent=4)

    def aggiungi_punti(self, nome_collaboratore, azione):
        """
        Aggiunge un'azione completata a un collaboratore.
        """
        nome = nome_collaboratore.strip().title()
        
        punti_da_aggiungere = self.punti_azioni.get(azione, 0)
        
        if punti_da_aggiungere == 0:
            return f"Errore: Azione '{azione}' non riconosciuta."

        if nome not in self.dati_collaboratori:
            self.dati_collaboratori[nome] = []
        
        self.dati_collaboratori[nome].append({
            "azione": azione,
            "punti": punti_da_aggiungere,
            "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        self.salva_dati()
        self.genera_report_html() # Genera il report automaticamente
        return f"Aggiunta l'azione '{azione}' a {nome} (+{punti_da_aggiungere} punti)."

    def elimina_riga(self, nome_collaboratore, indice_riga):
        """
        Elimina una riga specifica dall'elenco delle azioni di un collaboratore.
        L'indice della riga parte da 0.
        """
        nome = nome_collaboratore.strip().title()
        
        if nome not in self.dati_collaboratori:
            return f"Errore: Il collaboratore '{nome}' non esiste."
        
        if not (0 <= indice_riga < len(self.dati_collaboratori[nome])):
            return f"Errore: L'indice di riga {indice_riga + 1} non è valido per il collaboratore '{nome}'."

        azione_rimossa = self.dati_collaboratori[nome].pop(indice_riga)
        self.salva_dati()
        self.genera_report_html() # Genera il report automaticamente
        
        return f"Rimossa l'azione '{azione_rimossa['azione']}' del collaboratore {nome} (rimossi {azione_rimossa['punti']} punti)."
        
    def elimina_collaboratore(self, nome_collaboratore):
        """
        Elimina un collaboratore e tutti i suoi dati dalla classifica.
        """
        nome = nome_collaboratore.strip().title()
        if nome in self.dati_collaboratori:
            del self.dati_collaboratori[nome]
            self.salva_dati()
            self.genera_report_html() # Genera il report automaticamente
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

        classifica_list = ["--- CLASSIFICA APEX CHALLENGE ---"]
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
        nome = nome_collaboratore.strip().title()
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
        aggiungendo il logo Ubroker e le colorazioni aziendali e rendendolo responsive.
        """
        # Definisco i colori di Ubroker
        colore_primario = "#0d47a1"  # Blu Ubroker
        colore_secondario = "#ff6f00" # Arancione/Oro Ubroker

        if not self.dati_collaboratori:
            report_content = f"""
            <!DOCTYPE html>
            <html lang="it">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Classifica Apex Challenge</title>
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
                        background: linear-gradient(to right, #e3f2fd, #ffffff);
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
                        margin-bottom: 20px;
                    }}
                    .logo {{
                        max-width: 250px;
                        height: auto;
                    }}
                    h1 {{
                        text-align: center;
                        color: {colore_primario};
                        text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.1);
                        font-size: 2.5em;
                        margin-bottom: 5px;
                    }}
                    h2 {{
                        text-align: center;
                        color: #555;
                        font-size: 1.5em;
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
                    <h1>CLASSIFICA APEX CHALLENGE</h1>
                    <h2>Classifica Generale</h2>
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
            </body>
            </html>
            """
            report_content = html_content
            
        report_filename = "index.html"
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write(report_content)
        
        return f"Report HTML generato con successo. Lo trovi nel file '{report_filename}'."

# --- INTERFACCIA GRAFICA CON PYSIMPLEGUI ---
if __name__ == "__main__":
    manager = ClassificaManager()
    
    # Genera il report iniziale all'avvio del programma
    manager.genera_report_html()
    
    azioni_disponibili = list(manager.punti_azioni.keys())
    dettaglio_attivo_per = None

    # INSERISCI QUI L'URL PUBBLICO DEL TUO REPORT ONLINE
    # ESEMPIO: "https://miosito.it/classifica_apex_report.html"
    URL_REPORT_ONLINE = "https://davidezero.github.io/apex-challenge-report/"
    
    layout = [
        [sg.Text("CLASSIFICA APEX CHALLENGE", size=(30, 1), justification='center', font=("Helvetica", 16), text_color='orange')],
        [sg.HorizontalSeparator()],
        [sg.Text("Aggiungi Punti", font=("Helvetica", 12))],\
        [sg.Text("Nome Collaboratore:", size=(18, 1)), sg.Input(key='-NOME-', size=(25, 1))],\
        [sg.Text("Azione:", size=(18, 1)), sg.Combo(azioni_disponibili, default_value=azioni_disponibili[0] if azioni_disponibili else '', key='-AZIONE-', size=(23, 1))],\
        [sg.Button("Aggiungi", key='-AGGIUNGI-')],\
        [sg.HorizontalSeparator()],\
        [sg.Text("Visualizza e Modifica Classifica", font=("Helvetica", 12))],\
        [sg.Listbox(values=manager.mostra_classifica(), size=(60, 15), key='-LISTA_CLASSIFICA-', enable_events=True)],\
        [sg.Text("Nome Collaboratore:", size=(18, 1)), sg.Input(key='-NOME_SELEZIONATO-', size=(25, 1))],\
        [sg.Button("Mostra Dettaglio", key='-MOSTRA_DETTAGLIO-'), sg.Button("Mostra Classifica Totale", key='-MOSTRA_TOTALE-')],\
        [sg.Button("Elimina Riga Selezionata", key='-ELIMINA_RIGA-'), sg.Button("Elimina Collaboratore", key='-ELIMINA_COLLABORATORE-')],\
        [sg.HorizontalSeparator()],\
        [sg.Button("Genera Report HTML", key='-REPORT-'), sg.Button("Condividi su WhatsApp", key='-WHATSAPP-'), sg.Button("Apri Report Online", key='-APRI_REPORT-'), sg.Button("Carica su GitHub", key='-CARICA_GITHUB-'), sg.Button("Esci", key='-ESCI-')]\
    ]

    window = sg.Window("Apex Challenge Manager", layout, finalize=True)
    
    while True:
        event, values = window.read()
        
        if event == sg.WIN_CLOSED or event == '-ESCI-':
            break

        if event == '-AGGIUNGI-':
            nome = values['-NOME-'].strip().title()
            azione_scelta = values['-AZIONE-']
            
            if not nome:
                sg.popup_error("Errore: Inserisci un nome per il collaboratore.")
            elif not azione_scelta:
                sg.popup_error("Errore: Seleziona un'azione.")
            else:
                messaggio = manager.aggiungi_punti(nome, azione_scelta)
                sg.popup_ok(messaggio)
                window['-LISTA_CLASSIFICA-'].update(manager.mostra_classifica())
                dettaglio_attivo_per = None
                window['-NOME_SELEZIONATO-'].update('')
        
        if event == '-MOSTRA_DETTAGLIO-':
            nome_dettaglio = values['-NOME_SELEZIONATO-'].strip().title()
            if not nome_dettaglio:
                sg.popup_error("Errore: Inserisci un nome per mostrare il dettaglio.")
            else:
                dettaglio_list = manager.mostra_dettaglio_classifica(nome_dettaglio)
                if dettaglio_list[0].startswith('Errore'):
                    sg.popup_error(dettaglio_list[0])
                else:
                    window['-LISTA_CLASSIFICA-'].update(dettaglio_list)
                    dettaglio_attivo_per = nome_dettaglio
                    
        if event == '-MOSTRA_TOTALE-':
            window['-LISTA_CLASSIFICA-'].update(manager.mostra_classifica())
            dettaglio_attivo_per = None
            window['-NOME_SELEZIONATO-'].update('')

        if event == '-ELIMINA_RIGA-':
            if dettaglio_attivo_per and values['-LISTA_CLASSIFICA-']:
                riga_da_eliminare_str = values['-LISTA_CLASSIFICA-'][0]
                try:
                    indice_da_eliminare = int(riga_da_eliminare_str.split(']')[0].replace('[','').strip()) - 1
                    messaggio = manager.elimina_riga(dettaglio_attivo_per, indice_da_eliminare)
                    sg.popup_ok(messaggio)
                    
                    dettaglio_list = manager.mostra_dettaglio_classifica(dettaglio_attivo_per)
                    window['-LISTA_CLASSIFICA-'].update(dettaglio_list)
                    
                except (ValueError, IndexError):
                    sg.popup_error("Errore: Seleziona una riga valida (es. [1]) dal dettaglio per eliminarla.")
            else:
                sg.popup_error("Errore: Prima devi visualizzare il dettaglio di un collaboratore e selezionare una riga.")

        if event == '-ELIMINA_COLLABORATORE-':
            nome_elimina = values['-NOME_SELEZIONATO-'].strip().title()
            if not nome_elimina:
                 sg.popup_error("Errore: Inserisci il nome del collaboratore da eliminare.")
            else:
                conferma = sg.popup_yes_no(f"Sei sicuro di voler eliminare il collaboratore '{nome_elimina}' e tutti i suoi dati?", title="Conferma Eliminazione")
                if conferma == 'Yes':
                    messaggio = manager.elimina_collaboratore(nome_elimina)
                    sg.popup_ok(messaggio)
                    window['-LISTA_CLASSIFICA-'].update(manager.mostra_classifica())
                    dettaglio_attivo_per = None
                    window['-NOME_SELEZIONATO-'].update('')

        if event == '-REPORT-':
            messaggio = manager.genera_report_html()
            sg.popup_ok(messaggio)
        
        if event == '-WHATSAPP-':
            if URL_REPORT_ONLINE:
                messaggio = f"Ciao a tutti! La classifica Apex Challenge è stata aggiornata! Cliccate qui per vederla in tempo reale: {URL_REPORT_ONLINE}"
                whatsapp_url = f"https://api.whatsapp.com/send?text={quote(messaggio)}"
                webbrowser.open(whatsapp_url)
            else:
                sg.popup_ok("Devi prima inserire l'URL pubblico del tuo report nel codice, nella variabile 'URL_REPORT_ONLINE'.")

        if event == '-APRI_REPORT-':
            if URL_REPORT_ONLINE:
                webbrowser.open(URL_REPORT_ONLINE)
            else:
                sg.popup_ok("Devi prima inserire l'URL pubblico del tuo report nel codice, nella variabile 'URL_REPORT_ONLINE'.")
        
        if event == '-CARICA_GITHUB-':
            try:
                # Esegue i comandi Git per aggiornare il repository online
                sg.popup_ok("Sto caricando su GitHub. Attendi...")
                subprocess.run(["git", "add", "index.html"], check=True)
                subprocess.run(["git", "add", "logo_ubroker.png"], check=True)
                subprocess.run(["git", "commit", "-m", "Aggiornata classifica"], check=True)
                subprocess.run(["git", "push"], check=True)
                sg.popup_ok("La classifica è stata caricata su GitHub e verrà aggiornata online a breve.")
            except subprocess.CalledProcessError as e:
                sg.popup_error(f"Errore durante l'aggiornamento su GitHub: {e.stderr.decode()}")
            except FileNotFoundError:
                sg.popup_error("Errore: Git non è stato trovato. Assicurati che sia installato e configurato.")

    window.close()