import pandas as pd

def generer_resume(resultats_analyses):
    if not resultats_analyses:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), 0

    df = pd.DataFrame(resultats_analyses)
    if 'date' not in df.columns or df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), 0
        
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)

    # On ne garde que les jours où il y a eu au moins un écart calculé
    df_valide = df.dropna(subset=['ecart_matin', 'ecart_soir'], how='all').copy()
    
    jours_analyses = len(df_valide)

    def to_minutes(td):
        return td.total_seconds() / 60 if pd.notna(td) else 0

    df_valide['ecart_matin_min'] = df_valide['ecart_matin'].apply(to_minutes)
    df_valide['ecart_soir_min'] = df_valide['ecart_soir'].apply(to_minutes)
    
    # Calcul des MOYENNES
    moyenne_semaine = df_valide.resample('W-MON', label='left', closed='left').agg({'ecart_matin_min': 'mean', 'ecart_soir_min': 'mean'})
    moyenne_mois = df_valide.resample('M').agg({'ecart_matin_min': 'mean', 'ecart_soir_min': 'mean'})
    
    # Calcul des SOMMES (pour le mois seulement)
    total_mois = df_valide.resample('M').agg({'ecart_matin_min': 'sum', 'ecart_soir_min': 'sum'})
    
    return moyenne_semaine, moyenne_mois, total_mois, jours_analyses