# gui.py

import sys
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QButtonGroup, QFrame, QStackedWidget,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QScrollArea, QComboBox, QGridLayout
)
# --- AJOUT: Importer pyqtSignal pour la communication entre widgets ---
from PyQt6.QtCore import Qt, QRect, QPropertyAnimation, QEasingCurve, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QFontMetrics, QAction

import analyse_core
import resume_ecart

def format_timedelta_display(td):
    if pd.isna(td): return "N/A"
    total_seconds = int(td.total_seconds())
    sign = '-' if total_seconds < 0 else ''
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{sign}{hours:02}:{minutes:02}:{seconds:02}"

class DetailsPageWidget(QWidget):
    # --- AJOUT: Signal pour notifier la fenêtre principale de lancer l'analyse ---
    analyse_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        self.mapping_frame = QFrame()
        self.mapping_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.mapping_layout = QVBoxLayout(self.mapping_frame)
        self.mapping_frame.hide()
        self.main_layout.addWidget(self.mapping_frame)
        self.employee_truck_combos = {}
        self.details_display = QTextEdit()
        self.details_display.setReadOnly(True)
        self.details_display.setFont(QFont("Calibri", 15))
        self.main_layout.addWidget(self.details_display)
        self.display_message("👋 Bienvenue ! Chargez les fichiers de pointage et GPS pour commencer.")

    def setup_truck_mapping_ui(self, employee_names, truck_plates):
        while self.mapping_layout.count():
            child = self.mapping_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.employee_truck_combos.clear()
        
        title = QLabel("Associer un camion à chaque employé pour l'analyse :")
        title.setFont(QFont("Calibri", 15, QFont.Weight.Bold))
        self.mapping_layout.addWidget(title)

        grid = QGridLayout()
        options = ["Aucun"] + sorted(truck_plates)
        
        for i, name in enumerate(sorted(employee_names)):
            label = QLabel(name)
            label.setFont(QFont("Calibri", 15))
            combo = QComboBox()
            combo.addItems(options)
            combo.setFixedWidth(200)
            grid.addWidget(label, i, 0)
            grid.addWidget(combo, i, 1)
            self.employee_truck_combos[name] = combo
            
        self.mapping_layout.addLayout(grid)
        
        # --- AJOUT: Création et ajout du bouton "Lancer l'analyse" ---
        self.lancer_analyse_button = QPushButton("Lancer l'analyse")
        self.lancer_analyse_button.setFont(QFont("Calibri", 15, QFont.Weight.Bold))
        self.lancer_analyse_button.setFixedWidth(200)
        self.lancer_analyse_button.setStyleSheet("""
            QPushButton { 
                background-color: #2128F5; 
                color: white; 
                padding: 8px; 
                border-radius: 5px;
                margin-top: 10px;
            }
            QPushButton:hover { background-color: #2128F5; }
        """)
        # On connecte le clic du bouton à l'émission de notre signal personnalisé
        self.lancer_analyse_button.clicked.connect(self.analyse_requested.emit)
        self.mapping_layout.addWidget(self.lancer_analyse_button)
        # --- FIN DE L'AJOUT ---

        self.mapping_frame.show()
        self.display_message("Veuillez effectuer les associations puis cliquer sur le bouton \"Lancer l'analyse\".")

    def get_truck_assignments(self):
        assignments = {}
        for name, combo in self.employee_truck_combos.items():
            assignments[name] = combo.currentText()
        return assignments

    def clear_display(self):
        self.details_display.clear()
        self.mapping_frame.hide()

    def display_message(self, message):
        self.details_display.setText(message)

    def afficher_rapport(self, resultats, nom_employe, plaque_camion, append=False):
        if not resultats: return

        header = f"👤 Employé : {nom_employe}\n"
        header += f"🚚 Camion assigné : {plaque_camion}\n"
        header += "="*50 + "\n\n"
        
        body = ""
        for res in sorted(resultats, key=lambda x: x['date']):
            body += f"--- Journée du {res['date']:%d/%m/%Y} ---\n"
            body += f"Pointage         : {res['pointage_debut']:%H:%M} - {res['pointage_fin']:%H:%M}\n"
            body += f"Temps de travail : {format_timedelta_display(res.get('temps_travail', pd.NaT))}\n"
            body += f"Temps de pause   : {format_timedelta_display(res.get('temps_pause', pd.NaT))}\n"
            arrivee = res['gps_arrivee'].strftime('%H:%M') if pd.notna(res['gps_arrivee']) else 'N/A'
            depart = res['gps_depart'].strftime('%H:%M') if pd.notna(res['gps_depart']) else 'N/A'
            body += f"GPS (Arr/Dep)    : {arrivee} - {depart}\n"
            body += f"  -> Ecart Matin   : {format_timedelta_display(res['ecart_matin'])}\n"
            body += f"  -> Ecart Soir    : {format_timedelta_display(res['ecart_soir'])}\n\n"
        
        full_report = header + body

        if append:
            current_text = self.details_display.toPlainText()
            messages_a_effacer = ["Veuillez effectuer les associations", "Bienvenue", "Analyse en cours..."]
            if any(msg in current_text for msg in messages_a_effacer):
                current_text = ""
            separator = "\n\n" + "#"*60 + "\n\n" if current_text else ""
            self.details_display.setText(current_text + separator + full_report)
        else:
            self.details_display.setText(full_report)


class ResumePageWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.employee_selector = QComboBox()
        self.employee_selector.setFont(QFont("Calibri", 15))
        self.employee_selector.setFixedWidth(200)
        self.employee_selector.currentIndexChanged.connect(self.update_summary_view)
        self.main_layout.addWidget(self.employee_selector)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; }")
        self.scroll_content = QWidget()
        self.content_layout = QVBoxLayout(self.scroll_content)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.scroll_content)
        self.main_layout.addWidget(self.scroll_area)
        self.employee_summaries = {}
        self.is_first_summary = True
        self.clear_display()

    def clear_display(self):
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.employee_summaries.clear()
        self.employee_selector.clear()
        self.employee_selector.hide()
        self.is_first_summary = True
        self.initial_label = QLabel("Lancez une analyse pour voir les résumés.")
        self.initial_label.setFont(QFont("Calibri", 14, QFont.Weight.Bold))
        self.initial_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.initial_label)

    def afficher_resume(self, resumes, nom_employe, plaque_camion):
        moyenne_semaine, moyenne_mois, total_mois, jours = resumes
        if jours == 0: return

        if self.is_first_summary:
            self.is_first_summary = False
            self.initial_label.hide()
            self.employee_selector.addItem("Tous les employés")
            self.employee_selector.show()

        employee_frame = QFrame()
        employee_frame.setFrameShape(QFrame.Shape.StyledPanel)
        employee_layout = QVBoxLayout(employee_frame)
        stats_label = QLabel(
            f"👤 <b>{nom_employe}</b> | 🚚 <b>{plaque_camion}</b><br>"
            f"Nombre de jours analysés (avec écarts) : {jours}"
        )
        stats_label.setFont(QFont("Calibri", 14, QFont.Weight.Bold))
        employee_layout.addWidget(stats_label)
        employee_layout.addWidget(QLabel("Moyennes par semaine :"))
        semaine_table = QTableWidget()
        employee_layout.addWidget(semaine_table)
        employee_layout.addWidget(QLabel("Moyennes & totaux par mois :"))
        mois_table = QTableWidget()
        employee_layout.addWidget(mois_table)
        table_font = QFont("Calibri", 11)
        semaine_table.setFont(table_font)
        mois_table.setFont(table_font)
        self._remplir_table(semaine_table, moyenne_semaine, "Semaine du", "Moyenne")
        self._remplir_table(mois_table, moyenne_mois, "Mois de", "Moyenne", total_mois)
        self.employee_summaries[nom_employe] = employee_frame
        self.content_layout.addWidget(employee_frame)
        self.employee_selector.addItem(nom_employe)

    def update_summary_view(self):
        selected_employee = self.employee_selector.currentText()
        if not selected_employee: return
        for name, frame in self.employee_summaries.items():
            is_visible = (selected_employee == "Tous les employés" or name == selected_employee)
            frame.setVisible(is_visible)

    def _remplir_table(self, table, df_moyenne, prefix, type_calcul, df_total=None):
        if df_moyenne.empty:
            table.hide()
            return
        df_moyenne.index = df_moyenne.index.strftime('%Y-%m-%d')
        if 'Mois' in prefix:
            df_moyenne.index = pd.to_datetime(df_moyenne.index).strftime('%B %Y')
        headers = [prefix, f"{type_calcul} Écart matin", f"{type_calcul} Écart soir"]
        if df_total is not None:
            headers.extend(["Total écart matin", "Total écart soir"])
        table.clearContents()
        table.setRowCount(len(df_moyenne))
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        for row, (index, data) in enumerate(df_moyenne.iterrows()):
            table.setItem(row, 0, QTableWidgetItem(str(index)))
            moy_matin = pd.to_timedelta(data.get('ecart_matin_min', 0), unit='m')
            moy_soir = pd.to_timedelta(data.get('ecart_soir_min', 0), unit='m')
            table.setItem(row, 1, QTableWidgetItem(format_timedelta_display(moy_matin)))
            table.setItem(row, 2, QTableWidgetItem(format_timedelta_display(moy_soir)))
            if df_total is not None:
                total_data = df_total.loc[df_total.index.strftime('%B %Y') == index]
                if not total_data.empty:
                    tot_matin = pd.to_timedelta(total_data['ecart_matin_min'].iloc[0], unit='m')
                    tot_soir = pd.to_timedelta(total_data['ecart_soir_min'].iloc[0], unit='m')
                    table.setItem(row, 3, QTableWidgetItem(format_timedelta_display(tot_matin)))
                    table.setItem(row, 4, QTableWidgetItem(format_timedelta_display(tot_soir)))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)


class AnalyseurMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Analyseur d'écarts pointage/GPS")
        self.resize(800, 600)
        self.paths_pointage = []
        self.paths_gps = []
        self.donnees_employes = {}
        self.donnees_gps_par_camion = {}
        self._setup_ui()
        self._setup_menu()
        self.tab_button_group.buttonClicked.connect(self.switch_tab)
        QTimer.singleShot(0, lambda: self.tab_buttons["Détail par jour"].click())
        
        # --- AJOUT: On connecte le signal du widget de détail à la fonction d'analyse ---
        self.page_details.analyse_requested.connect(self.lancer_analyse_globale)

    def _setup_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setCentralWidget(main_widget)
        self._create_tabs_and_underline(main_layout)
        self._create_main_pages(main_layout)

    def _create_tabs_and_underline(self, parent_layout):
        self.tab_container = QWidget()
        self.tab_container.setFixedHeight(40)
        tab_bar_layout = QHBoxLayout(self.tab_container)
        tab_bar_layout.setSpacing(0)
        tab_bar_layout.setContentsMargins(20, 0, 0, 0)
        self.tab_buttons = {}
        self.tab_button_group = QButtonGroup(self)
        self.tab_button_group.setExclusive(True)
        for i, name in enumerate(["Détail par jour", "Résumé"]):
            btn = QPushButton(name)
            btn.setFont(QFont("Calibri", 11))
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton { border: none; background: transparent; color: #444444; padding: 10px 15px; }
                QPushButton:hover { background: #e6e6e6; }
                QPushButton:checked { color: #000000; font-weight: bold; }
            """)
            metrics = QFontMetrics(QFont("Calibri", 11, QFont.Weight.Bold))
            btn.setFixedWidth(metrics.horizontalAdvance(name) + 30)
            tab_bar_layout.addWidget(btn)
            self.tab_buttons[name] = btn
            self.tab_button_group.addButton(btn, i)
        tab_bar_layout.addStretch()
        self.underline = QFrame(self.tab_container)
        self.underline.setFixedHeight(3)
        self.underline.setStyleSheet("background-color: #4169E1;")
        parent_layout.addWidget(self.tab_container)

    def _create_main_pages(self, parent_layout):
        self.pages = QStackedWidget()
        self.page_details = DetailsPageWidget()
        self.page_resume = ResumePageWidget()
        self.pages.addWidget(self.page_details)
        self.pages.addWidget(self.page_resume)
        parent_layout.addWidget(self.pages)
    
    def _setup_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Fichier")
        action_pointage = QAction("Charger fichiers pointage", self)
        action_pointage.triggered.connect(self.select_fichier_pointage)
        file_menu.addAction(action_pointage)
        action_gps = QAction("Charger fichiers GPS", self)
        action_gps.triggered.connect(self.select_fichiers_gps)
        file_menu.addAction(action_gps)
    
    def _update_file_load_status(self):
        pointage_ok = bool(self.donnees_employes)
        gps_ok = bool(self.donnees_gps_par_camion)

        self.page_details.mapping_frame.hide()

        if pointage_ok and gps_ok:
            employee_names = list(self.donnees_employes.keys())
            truck_plates = list(self.donnees_gps_par_camion.keys())
            self.page_details.setup_truck_mapping_ui(employee_names, truck_plates)
        elif pointage_ok:
            message = f"✅ {len(self.donnees_employes)} employé(s) chargé(s) depuis le fichier de pointage.\n\n" \
                      f"--> Veuillez maintenant charger le(s) fichier(s) GPS."
            self.page_details.display_message(message)
        elif gps_ok:
            message = f"✅ {len(self.donnees_gps_par_camion)} camion(s) chargé(s) depuis les fichiers GPS.\n\n" \
                      f"--> Veuillez maintenant charger le fichier de pointage."
            self.page_details.display_message(message)
        else:
            self.page_details.display_message("👋 Bienvenue ! Chargez les fichiers pour commencer.")

    def select_fichier_pointage(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Sélectionner le(s) fichier(s) de pointage", "", "Fichiers Excel (*.xlsx *.xls)")
        if file_paths:
            self.paths_pointage = file_paths
            try:
                self.donnees_employes = analyse_core.charger_fichier_pointage(self.paths_pointage)
                self._update_file_load_status()
            except Exception as e:
                self.page_details.display_message(f"❌ Erreur lors du chargement du fichier pointage:\n{e}")

    def select_fichiers_gps(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Sélectionner le(s) fichier(s) GPS", "", "Fichiers Excel (*.xlsx *.xls)")
        if file_paths:
            self.paths_gps = file_paths
            try:
                self.donnees_gps_par_camion = analyse_core.charger_fichiers_gps(self.paths_gps)
                self._update_file_load_status()
            except Exception as e:
                self.page_details.display_message(f"❌ Erreur lors du chargement des fichiers GPS:\n{e}")

    def lancer_analyse_globale(self):
        if not self.donnees_employes or not self.donnees_gps_par_camion:
            self.page_details.display_message("Veuillez d'abord charger les fichiers de pointage et les fichiers GPS.")
            return

        assignments = self.page_details.get_truck_assignments()
        
        self.page_details.display_message("Analyse en cours...")
        self.page_resume.clear_display()
        QApplication.processEvents()

        has_results = False
        for nom_employe, df_employe in sorted(self.donnees_employes.items()):
            assigned_truck = assignments.get(nom_employe)
            if assigned_truck and assigned_truck != "Aucun":
                has_results = True
                gps_data_for_truck = self.donnees_gps_par_camion.get(assigned_truck, {})
                resultats = analyse_core.analyser_donnees(df_employe, gps_data_for_truck, nom_employe, assigned_truck)
                resumes = resume_ecart.generer_resume(resultats)
                self.page_details.afficher_rapport(resultats, nom_employe, assigned_truck, append=True)
                self.page_resume.afficher_resume(resumes, nom_employe, assigned_truck)
        
        if not has_results:
            self.page_details.display_message("Aucune association employé-camion n'a été faite ou aucun employé n'a de données valides. L'analyse n'a pas pu être complétée.")
            return

        self.statusBar().showMessage("✅ Analyse terminée.", 5000)
        self.tab_buttons["Résumé"].click()

    def switch_tab(self, button):
        self.pages.setCurrentIndex(self.tab_button_group.id(button))
        self._update_underline_position(animate=True)

    def _update_underline_position(self, animate=False):
        active_button = self.tab_button_group.checkedButton()
        if not active_button: return
        target_rect = QRect(active_button.pos().x(), self.tab_container.height() - 3, active_button.width(), 3)
        if animate and hasattr(self, 'underline') and self.underline.width() > 0:
            self.animation = QPropertyAnimation(self.underline, b"geometry")
            self.animation.setDuration(250); self.animation.setEndValue(target_rect); self.animation.start()
        else: self.underline.setGeometry(target_rect)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._update_underline_position)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = AnalyseurMainWindow()
    window.show()
    sys.exit(app.exec())