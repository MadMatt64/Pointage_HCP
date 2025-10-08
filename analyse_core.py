# analyse_core.py

import pandas as pd
import datetime
import os

# La fonction charger_fichier_pointage reste inchangée
def charger_fichier_pointage(file_paths):
    """
    Charge un ou plusieurs fichiers de pointage, les concatène,
    et retourne un dictionnaire de DataFrames, un par employé.
    """
    all_dfs = []
    for file_path in file_paths:
        try:
            df = pd.read_excel(file_path, sheet_name=0, header=1)
            if not df.empty:
                df.columns = df.columns.str.strip()
                all_dfs.append(df)
        except Exception as e:
            raise ValueError(f"Erreur lors de la lecture du fichier {file_path}. Assurez-vous que le format est correct. Détail: {e}")

    if not all_dfs:
        return {}

    combined_df = pd.concat(all_dfs, ignore_index=True)

    if 'Nom' not in combined_df.columns or 'Prénom' not in combined_df.columns:
        raise ValueError("Les colonnes 'Nom' et 'Prénom' sont introuvables dans les fichiers de pointage. Veuillez vérifier l'en-tête.")

    combined_df.dropna(subset=['Nom', 'Prénom'], inplace=True)
    combined_df['Nom'] = combined_df['Nom'].astype(str).str.strip()
    combined_df['Prénom'] = combined_df['Prénom'].astype(str).str.strip()
    combined_df['nom_complet'] = combined_df['Prénom'] + ' ' + combined_df['Nom']

    combined_df['Entrée'] = pd.to_datetime(combined_df['Entrée'], dayfirst=True, errors='coerce')
    combined_df['Sortie'] = pd.to_datetime(combined_df['Sortie'], dayfirst=True, errors='coerce')
    combined_df.dropna(subset=['Entrée', 'Sortie'], inplace=True)

    employes_data = {name: group.copy() for name, group in combined_df.groupby('nom_complet')}
    return employes_data

# --- MODIFICATION MAJEURE DE CETTE FONCTION ---
def charger_fichiers_gps(file_paths):
    """
    Charge les fichiers GPS et retourne un dictionnaire de données GPS
    structuré par plaque d'immatriculation.
    Exemple de retour: { "Plaque1": { "date1": [trajets] }, "Plaque2": { ... } }
    """
    gps_data_by_plate = {}

    for file_path in file_paths:
        plaque = "Inconnue"
        try:
            filename = os.path.basename(file_path)
            parts = filename.replace('_', ' ').replace('-', ' ').split()
            idx = [p.lower() for p in parts].index("véhicule")
            plaque = " ".join(parts[idx+1:idx+4])
        except (ValueError, IndexError):
            # Si la plaque n'est pas trouvée, on passe au fichier suivant pour ce camion
            continue 
        
        # Si c'est la première fois qu'on voit cette plaque, on initialise son dictionnaire
        if plaque not in gps_data_by_plate:
            gps_data_by_plate[plaque] = {}

        xls = pd.ExcelFile(file_path)
        sheet_names_to_read = xls.sheet_names[1:6]
        for sheet_name in sheet_names_to_read:
            df_jour = pd.read_excel(xls, sheet_name=sheet_name, header=None)
            try:
                date_cell_value = df_jour.iloc[4, 1]
                if pd.isna(date_cell_value): continue
                date_obj = pd.to_datetime(date_cell_value, dayfirst=True)
                date_str = date_obj.strftime('%Y-%m-%d')
            except Exception: continue
            
            start_row_index = -1
            for row in df_jour.itertuples():
                if isinstance(row[2], str) and row[2].strip().startswith("Trajet n"):
                    start_row_index = row.Index + 1; break
            if start_row_index == -1: continue
            
            trajets_data = []
            for _, row in df_jour.iloc[start_row_index:].iterrows():
                if pd.notna(row[1]) and pd.notna(row[3]):
                    trajets_data.append({
                        'heure_depart': row[3], 
                        'heure_arrivee': row[5],
                        'lieu_arrivee': row[4]
                    })
                elif pd.isna(row[1]): break
            
            if trajets_data:
                # On ajoute les données de la journée à la bonne plaque
                gps_data_by_plate[plaque][date_str] = trajets_data

    return gps_data_by_plate

# La fonction analyser_donnees reste inchangée
def analyser_donnees(df_pointage, donnees_gps, nom_employe, plaque_camion):
    resultats_analyses = []
    pointages_par_jour = df_pointage.groupby(df_pointage['Entrée'].dt.date)

    for date_obj, group in pointages_par_jour:
        date_str = date_obj.strftime('%Y-%m-%d')
        travail = group[group['Type'] == 'travail']
        pause = group[group['Type'] == 'pause']
        if travail.empty: continue
        
        debut_journee = travail['Entrée'].min()
        fin_journee = travail['Sortie'].max()

        resultat_jour = {
            'date': date_obj, 
            'nom_employe': nom_employe,
            'plaque_camion': plaque_camion,
            'pointage_debut': debut_journee, 
            'pointage_fin': fin_journee,
            'temps_travail': (travail['Sortie'] - travail['Entrée']).sum(),
            'temps_pause': (pause['Sortie'] - pause['Entrée']).sum() if not pause.empty else pd.Timedelta(0),
            'gps_arrivee': pd.NaT, 'gps_depart': pd.NaT, 
            'ecart_matin': pd.NaT, 'ecart_soir': pd.NaT
        }

        if date_str in donnees_gps:
            trajets_du_jour = donnees_gps[date_str]
            if not trajets_du_jour: 
                resultats_analyses.append(resultat_jour)
                continue

            resultat_jour['gps_arrivee'] = pd.to_datetime(f"{date_str} {trajets_du_jour[0]['heure_arrivee'].strftime('%H:%M:%S')}")
            resultat_jour['ecart_matin'] = resultat_jour['gps_arrivee'] - resultat_jour['pointage_debut']
            
            dernier_depart_valide = pd.NaT
            for trajet in reversed(trajets_du_jour):
                lieu = str(trajet.get('lieu_arrivee', ""))
                try:
                    depart_dt = pd.to_datetime(f"{date_str} {trajet['heure_depart'].strftime('%H:%M:%S')}")
                    arrivee_dt = pd.to_datetime(f"{date_str} {trajet['heure_arrivee'].strftime('%H:%M:%S')}")
                    duree_minutes = (arrivee_dt - depart_dt).total_seconds() / 60
                except Exception:
                    duree_minutes = 0

                if duree_minutes >= 25 and "Gardanne" in lieu:
                    dernier_depart_valide = depart_dt
                    break
            
            if pd.notna(dernier_depart_valide):
                resultat_jour['gps_depart'] = dernier_depart_valide
                resultat_jour['ecart_soir'] = resultat_jour['pointage_fin'] - resultat_jour['gps_depart']

        resultats_analyses.append(resultat_jour)
    return resultats_analyses