"""
Internationalization (i18n) module for MorphoGenerator Tool.
"""

_CURRENT_LANG = "English"

TRANSLATIONS = {
    "English": {
        "nav_viewer": "GLB Viewer",
        "nav_params": "Morphogenerator\nParameters",
        "nav_plots": "Plot Correlation",
        "nav_settings": "Settings",
        "nav_guide": "Guide",
        "btn_help": "ⓘ Help",
        
        "guide_title": "MorphoGenerator Tool Guide",
        "guide_intro": "Welcome to the MorphoGenerator Tool. Use the sidebar to navigate between sections.",
        
        "guide_glb_title": "1. GLB Viewer",
        "guide_glb_text": "The GLB Viewer provides an interactive 3D environment to inspect your generated geometries. You can load a model, seamlessly rotate and zoom using your mouse, and apply precision clipping along the X, Y, or Z axes to analyze the internal cross-sections.",
        
        "guide_params_title": "2. Select Parameters",
        "guide_params_text": "The Parameters panel offers two powerful analysis modes:\n• Forward Mode: Input the number of petals (N) and the flow ratio (Q) to immediately predict performance metrics and view a streamline preview.\n• Inverse Mode: Specify a target metric and your desired value to automatically reverse-calculate the optimal N and Q design parameters.",
        
        "guide_plots_title": "3. Plot Correlation",
        "guide_plots_text": "The Plot Correlation module generates rich 2D and 3D data visualizations, illustrating the non-linear relationship between your input parameters (N, Q) and the resulting morphological metrics. You can also import external data points for validation and export the figures in high resolution.",
        
        "guide_settings_title": "4. Settings & Preferences",
        "guide_settings_text": "The Settings panel lets you customize the application's appearance and behavior. You can switch between Light and Dark mode, change the interface language, and adjust the default plot export preferences (such as format and DPI) to match your workflow.",
        
        "modal_glb_title": "GLB Viewer Help",
        "modal_glb_text": "• Use the mouse to rotate the 3D model.\n• Clipping: Select an axis (X, Y, Z) and drag the slider to cut the model.\n• Keep: Choose which side of the cut to keep (Top/Bottom).",
        
        "modal_params_title": "Select Parameters Help",
        "modal_params_text": "• Forward Mode: Set N (number of petals) and Q (slider) to predict output metrics.\n• Inverse Mode: Enter a target value and tolerance to reverse-calculate the best N and Q.",
        
        "modal_plots_title": "Plot Correlation Help",
        "modal_plots_text": "• Select Plot Type: 2D Line, 2D Scatter, or 3D Surface.\n• Select the metric on the Y/Z axis.\n• You can filter the N values for 2D plots.\n• Use the Save icon below the plot to export.",
        
        "settings_appearance": "Appearance",
        "settings_data": "Data Configuration",
        "settings_plot": "Default Plot Settings",
        "settings_about": "About",
        
        "language_select": "Language",
    },
    "Italian": {
        "nav_viewer": "Visualizzatore GLB",
        "nav_params": "Morphogenerator\nParameters",
        "nav_plots": "Grafici di Correlazione",
        "nav_settings": "Impostazioni",
        "nav_guide": "Guida",
        "btn_help": "ⓘ Aiuto",
        
        "guide_title": "Guida al MorphoGenerator Tool",
        "guide_intro": "Benvenuto nel MorphoGenerator Tool. Usa il menu laterale per navigare tra le varie sezioni dell'applicazione.",
        
        "guide_glb_title": "1. Visualizzatore GLB",
        "guide_glb_text": "Il Visualizzatore GLB offre un ambiente 3D interattivo per ispezionare le geometrie generate. Puoi caricare un modello, ruotarlo fluidamente e utilizzare gli strumenti di clipping lungo gli assi X, Y o Z per analizzare nel dettaglio le sezioni interne.",
        
        "guide_params_title": "2. Seleziona Parametri",
        "guide_params_text": "Il pannello Parametri offre due potenti modalità di analisi:\n• Forward Mode (Modalità Diretta): Inserisci il numero di petali (N) e il rapporto di flusso (Q) per prevedere istantaneamente le metriche di performance e visualizzare un'anteprima.\n• Inverse Mode (Modalità Inversa): Specifica una metrica obiettivo e il valore desiderato per calcolare automaticamente a ritroso i parametri di design ottimali N e Q.",
        
        "guide_plots_title": "3. Grafici di Correlazione",
        "guide_plots_text": "Il modulo dei grafici genera visualizzazioni dati 2D e 3D avanzate, illustrando le relazioni non lineari tra i parametri di input (N, Q) e le metriche morfologiche risultanti. È inoltre possibile importare punti dati esterni per la convalida ed esportare i grafici in alta risoluzione.",
        
        "guide_settings_title": "4. Impostazioni e Preferenze",
        "guide_settings_text": "Il pannello delle Impostazioni ti permette di personalizzare l'aspetto e il comportamento dell'applicazione. Puoi passare dalla modalità Chiara a quella Scura, cambiare la lingua dell'interfaccia e regolare le preferenze di esportazione dei grafici (come formato e DPI) per adattarle al tuo flusso di lavoro.",
        
        "modal_glb_title": "Aiuto: Visualizzatore GLB",
        "modal_glb_text": "• Usa il mouse per ruotare il modello 3D.\n• Clipping: Seleziona un asse (X, Y, Z) e usa lo slider per tagliare il modello.\n• Keep: Scegli quale parte del taglio mantenere (Top/Bottom).",
        
        "modal_params_title": "Aiuto: Seleziona Parametri",
        "modal_params_text": "• Forward Mode: Imposta N (numero di petali) e Q per calcolare le metriche.\n• Inverse Mode: Inserisci un target e una tolleranza per calcolare a ritroso N e Q ottimali.",
        
        "modal_plots_title": "Aiuto: Grafici",
        "modal_plots_text": "• Tipo di Grafico: Linea 2D, Scatter 2D o Superficie 3D.\n• Filtra i valori di N per i grafici 2D.\n• Usa l'icona di salvataggio per esportare il grafico.",
        
        "settings_appearance": "Aspetto",
        "settings_data": "Configurazione Dati",
        "settings_plot": "Impostazioni Grafici Predefinite",
        "settings_about": "Informazioni",
        
        "language_select": "Lingua",
    },
    "French": {
        "nav_viewer": "Visionneuse GLB",
        "nav_params": "Morphogenerator\nParameters",
        "nav_plots": "Corrélation des Tracés",
        "nav_settings": "Paramètres",
        "nav_guide": "Guide",
        "btn_help": "ⓘ Aide",
        
        "guide_title": "Guide du MorphoGenerator",
        "guide_intro": "Bienvenue dans le MorphoGenerator Tool. Utilisez le menu pour naviguer.",
        
        "guide_glb_title": "1. Visionneuse GLB",
        "guide_glb_text": "La visionneuse GLB offre un environnement 3D interactif pour inspecter vos géométries générées. Vous pouvez charger un modèle, le faire pivoter de manière fluide et appliquer des coupes de précision pour analyser les sections transversales internes.",
        
        "guide_params_title": "2. Sélectionner Paramètres",
        "guide_params_text": "• Mode Direct : Saisissez le nombre de pétales (N) et le rapport de flux (Q) pour prédire immédiatement les paramètres de performance.\n• Mode Inverse : Spécifiez une métrique cible pour calculer automatiquement à rebours les paramètres de conception optimaux (N, Q).",
        
        "guide_plots_title": "3. Corrélation des Tracés",
        "guide_plots_text": "Générez des visualisations de données 2D et 3D riches, illustrant la relation non linéaire entre vos paramètres d'entrée et les métriques morphologiques. Vous pouvez exporter les figures en haute résolution.",
        
        "guide_settings_title": "4. Paramètres & Préférences",
        "guide_settings_text": "Le panneau Paramètres vous permet de personnaliser l'apparence et le comportement de l'application. Vous pouvez basculer entre le mode Clair et Sombre, changer la langue et ajuster les préférences d'exportation de graphiques.",
        
        "modal_glb_title": "Aide Visionneuse GLB",
        "modal_glb_text": "• Utilisez la souris pour tourner le modèle.\n• Clipping: Coupez le modèle avec le curseur.",
        
        "modal_params_title": "Aide Sélectionner Paramètres",
        "modal_params_text": "• Mode Direct: Prédisez les résultats.\n• Mode Inverse: Trouvez les paramètres optimaux.",
        
        "modal_plots_title": "Aide Graphiques",
        "modal_plots_text": "• Créez des graphiques 2D/3D et exportez-les avec l'icône de sauvegarde.",
        
        "settings_appearance": "Apparence",
        "settings_data": "Configuration des Données",
        "settings_plot": "Paramètres de Graphique",
        "settings_about": "À propos",
        
        "language_select": "Langue",
    },
    "Spanish": {
        "nav_viewer": "Visor GLB",
        "nav_params": "Morphogenerator\nParameters",
        "nav_plots": "Correlación de Gráficos",
        "nav_settings": "Ajustes",
        "nav_guide": "Guía",
        "btn_help": "ⓘ Ayuda",
        
        "guide_title": "Guía de MorphoGenerator",
        "guide_intro": "Bienvenido a MorphoGenerator Tool. Usa la barra lateral para navegar por las diferentes secciones.",
        
        "guide_glb_title": "1. Visor GLB",
        "guide_glb_text": "El Visor GLB proporciona un entorno 3D interactivo para inspeccionar las geometrías generadas. Puedes cargar un modelo, rotarlo sin problemas y aplicar cortes de precisión para analizar las secciones transversales internas.",
        
        "guide_params_title": "2. Seleccionar Parámetros",
        "guide_params_text": "• Modo Directo: Ingresa el número de pétalos (N) y la tasa de flujo (Q) para predecir de inmediato las métricas de rendimiento.\n• Modo Inverso: Especifica una métrica objetivo para calcular automáticamente a la inversa los parámetros de diseño óptimos (N, Q).",
        
        "guide_plots_title": "3. Correlación de Gráficos",
        "guide_plots_text": "Genera visualizaciones de datos 2D y 3D detalladas, ilustrando la relación no lineal entre los parámetros de entrada y las métricas morfológicas. Puedes exportar las figuras en alta resolución.",
        
        "guide_settings_title": "4. Ajustes y Preferencias",
        "guide_settings_text": "El panel de Ajustes te permite personalizar la apariencia y el comportamiento de la aplicación. Puedes cambiar entre el modo Claro y Oscuro, cambiar el idioma y ajustar las preferencias de exportación de gráficos.",
        
        "modal_glb_title": "Ayuda Visor GLB",
        "modal_glb_text": "• Usa el ratón para rotar el modelo.\n• Clipping: Corta el modelo usando el control deslizante.",
        
        "modal_params_title": "Ayuda Parámetros",
        "modal_params_text": "• Modo Directo: Predice resultados.\n• Modo Inverso: Encuentra parámetros óptimos.",
        
        "modal_plots_title": "Ayuda Gráficos",
        "modal_plots_text": "• Crea gráficos 2D/3D y expórtalos con el icono de guardar.",
        
        "settings_appearance": "Apariencia",
        "settings_data": "Configuración de Datos",
        "settings_plot": "Ajustes de Gráficos",
        "settings_about": "Acerca de",
        
        "language_select": "Idioma",
    },
    "German": {
        "nav_viewer": "GLB-Viewer",
        "nav_params": "Morphogenerator\nParameters",
        "nav_plots": "Diagrammkorrelation",
        "nav_settings": "Einstellungen",
        "nav_guide": "Anleitung",
        "btn_help": "ⓘ Hilfe",
        
        "guide_title": "MorphoGenerator Anleitung",
        "guide_intro": "Willkommen beim MorphoGenerator Tool. Verwenden Sie die Seitenleiste zur Navigation zwischen den Bereichen.",
        
        "guide_glb_title": "1. GLB-Viewer",
        "guide_glb_text": "Der GLB-Viewer bietet eine interaktive 3D-Umgebung zur Überprüfung der generierten Geometrien. Sie können ein Modell laden, es nahtlos drehen und präzise Schnitte anwenden, um die inneren Querschnitte zu analysieren.",
        
        "guide_params_title": "2. Parameter Auswählen",
        "guide_params_text": "• Vorwärts-Modus: Geben Sie die Anzahl der Blütenblätter (N) und die Durchflussrate (Q) ein, um Leistungsmetriken sofort vorherzusagen.\n• Rückwärts-Modus: Geben Sie eine Zielmetrik ein, um automatisch die optimalen Designparameter (N, Q) rückwärts zu berechnen.",
        
        "guide_plots_title": "3. Diagrammkorrelation",
        "guide_plots_text": "Erstellen Sie umfangreiche 2D- und 3D-Datenvisualisierungen, die die nichtlineare Beziehung zwischen Eingabeparametern und morphologischen Metriken veranschaulichen. Sie können die Grafiken in hoher Auflösung exportieren.",
        
        "guide_settings_title": "4. Einstellungen & Präferenzen",
        "guide_settings_text": "Im Bereich Einstellungen können Sie das Erscheinungsbild und Verhalten der App anpassen. Wechseln Sie zwischen Hell- und Dunkelmodus, ändern Sie die Sprache und passen Sie die Exportpräferenzen für Diagramme an.",
        
        "modal_glb_title": "Hilfe GLB-Viewer",
        "modal_glb_text": "• Verwenden Sie die Maus, um das Modell zu drehen.\n• Clipping: Schneiden Sie das Modell mit dem Schieberegler.",
        
        "modal_params_title": "Hilfe Parameter",
        "modal_params_text": "• Vorwärts-Modus: Ergebnisse vorhersagen.\n• Rückwärts-Modus: Optimale Parameter finden.",
        
        "modal_plots_title": "Hilfe Diagramme",
        "modal_plots_text": "• Erstellen Sie 2D-/3D-Diagramme und exportieren Sie sie.",
        
        "settings_appearance": "Erscheinungsbild",
        "settings_data": "Datenkonfiguration",
        "settings_plot": "Diagrammeinstellungen",
        "settings_about": "Über",
        
        "language_select": "Sprache",
    }
}

AVAILABLE_LANGUAGES = list(TRANSLATIONS.keys())

def set_language(lang: str):
    global _CURRENT_LANG
    if lang in TRANSLATIONS:
        _CURRENT_LANG = lang

def get_language() -> str:
    return _CURRENT_LANG

def t(key: str) -> str:
    """Translate a key using the current language. Falls back to English, then to the key itself."""
    lang_dict = TRANSLATIONS.get(_CURRENT_LANG, TRANSLATIONS["English"])
    if key in lang_dict:
        return lang_dict[key]
    
    # Fallback to English
    eng_dict = TRANSLATIONS["English"]
    if key in eng_dict:
        return eng_dict[key]
    
    return key
