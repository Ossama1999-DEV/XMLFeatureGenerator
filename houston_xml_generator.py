#!/usr/bin/env python3
"""Houston METRORail feature-type XML generator (stdlib only; Python 3.9+)."""
from __future__ import annotations

import json
import re
import tkinter as tk
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import xml.etree.ElementTree as ET

APP_DIR = Path(__file__).resolve().parent
PRESETS_FILE = APP_DIR / 'presets.json'
NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_.-]*$')


@dataclass
class Signal:
    name: str = 'Signal_US_WS_NewSign'
    abbreviation: str = 'WSNEW'
    family: str = 'Wayside Signs'
    description: str = 'New Sign'
    width: str = 'x.x'
    height: str = 'x.x'
    depth: str = 'x.x'
    # Notes are intentionally NOT serialized into the project XML.
    notes: str = ''


def normalize_dimension(text: str) -> str:
    """Keep x.x or accept positive decimal meters (commas accepted)."""
    value = text.strip().replace(',', '.')
    if value.lower() in ('x.x', ''):
        return 'x.x'
    try:
        number = float(value)
    except ValueError as ex:
        raise ValueError(f"Dimension invalide : {text!r}. Utilise x.x ou un nombre en mètres.") from ex
    if not (0 < number < 10000) or not re.fullmatch(r'\d+(?:\.\d+)?', value):
        raise ValueError(f"Dimension invalide : {text!r}. Une dimension doit être positive.")
    return value


def build_xml(signal: Signal) -> str:
    if not NAME_RE.fullmatch(signal.name):
        raise ValueError('Nom technique invalide : lettres, chiffres, _ . - uniquement.')
    if not signal.abbreviation.strip():
        raise ValueError("L'abréviation est obligatoire.")
    if not signal.family.strip() or not signal.description.strip():
        raise ValueError('Famille et description obligatoires.')
    width = normalize_dimension(signal.width)
    height = normalize_dimension(signal.height)
    depth = normalize_dimension(signal.depth)
    root = ET.Element('feature_type', {
        'name': signal.name, 'group': 'Signals',
        'constant_name': 'FETY_' + signal.name.upper(),
        'modifiable': '1', 'available': '1', 'user_feature': '0'
    })
    props = ET.SubElement(root, 'feature_type_properties')
    descs = ET.SubElement(props, 'descriptions')
    ET.SubElement(descs, 'abbreviation', {'name': signal.abbreviation.strip()})
    ET.SubElement(descs, 'family', {'name': signal.family.strip()})
    ET.SubElement(descs, 'description', {'name': signal.description.strip()})
    ET.SubElement(props, 'size', {'width': width, 'height': height, 'depth': depth, 'unit': 'meter'})
    state_type = ET.SubElement(root, 'feature_type_state_type', {'name': 'State'})
    ET.SubElement(state_type, 'feature_type_state', {
        'state_id': '1', 'name': 'Visible', 'user_selectable': '1'
    })
    params = ET.SubElement(root, 'object_parameters')
    ET.SubElement(params, 'key', {
        'name': 'Initial State', 'type': 'State', 'default': 'Visible',
        'world_editor_2d': 'editable', 'scenario_editor': 'editable', 'session': 'editable'
    })
    ET.SubElement(params, 'key', {
        'name': 'Virtual', 'type': 'double', 'default': '0', 'description': 'Virtual',
        'world_editor_2d': 'hidden', 'scenario_editor': 'hidden', 'session': 'hidden'
    })
    base = f'Icons/{signal.name}/{signal.name}'
    icons = ET.SubElement(root, 'feature_type_icon', {
        'icon_code': signal.name, 'small_icon': base + '-SMALL.png',
        'big_icon': base + '-BIG.png'
    })
    ET.SubElement(icons, 'feature_type_state_icon', {
        'state_id': '1', 'icon_code': 'Visible',
        'small_icon': base + '-SMALL.png', 'big_icon': base + '-BIG.png'
    })
    ET.SubElement(root, 'feature_type_vision', {
        'class': 'SwitchablePartFeature', 'raycast_type': 'NoRaycast',
        'node_file': signal.name + '.node'
    })
    ET.indent(root, space='  ')
    return "<?xml version='1.0' encoding='UTF-8'?>\n" + ET.tostring(root, encoding='unicode', short_empty_elements=True) + '\n'


class TableRowParser(HTMLParser):
    """Read a TR exported from the current Signals HTML catalog."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cells: list[str] = []
        self.in_cell = False
        self.cur: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'td':
            self.in_cell = True
            self.cur = []
        elif tag.lower() == 'br' and self.in_cell:
            self.cur.append(' ')

    def handle_endtag(self, tag):
        if tag.lower() == 'td' and self.in_cell:
            self.cells.append(' '.join(''.join(self.cur).split()))
            self.in_cell = False

    def handle_data(self, data):
        if self.in_cell:
            self.cur.append(data)


def parse_html_row(html: str) -> Signal:
    parser = TableRowParser()
    parser.feed(html)
    cells = parser.cells
    if len(cells) < 8:
        raise ValueError('Ligne HTML non reconnue : colle un <tr> contenant au moins 8 <td>.')
    name = cells[1]
    if not NAME_RE.fullmatch(name):
        raise ValueError('La 2e colonne du HTML ne contient pas un nom de signal valide.')
    dims = []
    for cell in cells[3:6]:
        matches = re.findall(r'(\d+(?:[.,]\d+)?)\s*m\b', cell, re.I)
        if matches:
            dims.append(matches[-1].replace(',', '.'))
        else:
            dims.append('x.x')
    return Signal(name=name, abbreviation=cells[2], width=dims[0], height=dims[1],
                  depth=dims[2], family=cells[6], description=cells[7],
                  notes='Importé depuis le tableau HTML (vérifier les dimensions).')


DEFAULT_PRESETS = [
    Signal('Signal_US_V_3L_S_1', 'V3LS1',
           family='Tramway signalisation',
           description='Vertical 3 Lights Straight',
           notes='Signal used for : Interlocking signals Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_V_3L_R_1', 'V3LR1',
           family='Tramway signalisation',
           description='Vertical 3 Lights Right',
           notes='Signal used for : Interlocking signals Bar signals Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_V_3L_L_1', 'V3LL1',
           family='Tramway signalisation',
           description='Vertical 3 Lights Left',
           notes='Signal used for : Interlocking signals Bar signals Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_V_2L_S_1', 'V2LS1',
           family='Tramway signalisation',
           description='Vertical 2 Lights Straight',
           notes='Signal used for : Interlocking signals Bar signals Grade Crossing Indicators Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_V_1L_1', 'V1L1',
           family='Tramway signalisation',
           description='(Vertical) 1 Light',
           notes='Signal used for : Interlocking signals Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_H_2L_S_1', 'H2LS1',
           family='Tramway signalisation',
           description='Horizontal 2 Lights Straight',
           notes='Signal used for : Bar signals Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_GradeCrossingIndicator', 'GCI',
           family='Tramway signalisation',
           description='Grade Crossing Indicator',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_SPI', 'SPI',
           family='Tramway signalisation',
           description='Switch Position Indicator',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_WS_BeginTestZone', 'WSBTZ',
           description='Begin Test Zone',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_WS_EndTestZone', 'WSETZ',
           description='End Test Zone',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_WS_YardLimit', 'WSYL',
           description='Yard Limit',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_WS_StopCallControl', 'WSSCC',
           description='Stop-Call Control',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_WS_SpeedLimitSign', 'WSSLS',
           description='Speed Limit Sign',
           width='0.457',
           height='0.457',
           notes='Editable speed value Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf Identified in the red line GX010003'),
    Signal('Signal_US_WS_SpeedLimitSignTrackSpecific', 'WSSLSTS',
           description='Speed Limit Sign (Track Specific)',
           width='0.457',
           height='0.609',
           notes='Editable track value Editable speed value Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf The text "TRACK 1" is modifiable. Identified in the red line GX010003'),
    Signal('Signal_US_WS_AdvanceSpeed', 'WSAS',
           description='Advance Speed',
           width='0.457',
           height='0.609',
           notes='Editable speed value Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_WS_AdvanceSpeedTrack', 'WSAST',
           description='Advance Speed Track',
           width='0.457',
           height='0.787',
           notes='Editable track value Editable speed value Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf Identified in the red line GX010003'),
    Signal('Signal_US_WS_DivergeSpeed', 'WSDS',
           description='Diverge Speed',
           width='0.457',
           height='0.609',
           notes='Editable speed value Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf Identified on the Red Line GX010006'),
    Signal('Signal_US_WS_HornSign', 'WSHS',
           description='Horn Sign',
           width='0.609',
           height='0.305',
           notes='Identified on the Red Line GX010003 and on the Green Line GX010009'),
    Signal('Signal_US_WS_Whistle', 'WSW',
           description='Whistle',
           width='0.305',
           height='0.305',
           notes='Identified in the red line GX010003'),
    Signal('Signal_US_WS_BeginBraking', 'WSBB',
           description='Begin Braking',
           notes='Identified in the Green line GX02008'),
    Signal('Signal_US_WS_NoClearance', 'WSNC',
           description='No Clearance',
           width='0.610',
           height='0.305',
           notes='Identified on the Red Line GX010003 and the Green Line GX010009 Estimated dimensions based on R5-10c (24 x 12 inches) - To be validated Source: Texas Standard Highway Sign Designs.pdf - Page 1-97'),
    Signal('Signal_US_WS_QuietZone', 'WSQZ',
           description='Quiet Zone',
           notes='Identified on the Red Line GX020003'),
    Signal('Signal_US_WS_ClearQuietZone', 'WSCQZ',
           description='Clear Quiet Zone',
           notes='Identified on the Red Line GX020003'),
    Signal('Signal_US_WS_InterlockingSign', 'WSIS',
           description='Interlocking Sign',
           notes='Editable 4 char size Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf Identified on the green Line GX010008 and olso HC1E -- Hobby Center (1 or 2) E ( Eastbound) (Interlocking Signals)'),
    Signal('Signal_US_WS_StationNameSign', 'WSSNS',
           description='Station Name Sign',
           notes='Editable Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_WS_GradeCrossingStreetNameSign', 'WSGCSNS',
           description='Grade Crossing Street Name Sign',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf Identified in the red line GX010003'),
    Signal('Signal_US_WS_SlowZoneMarker', 'WSSZM',
           description='Slow Zone Marker',
           width='0.152',
           height='0.305',
           notes='Editable speed value Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf Identified in the Green line GX020009'),
    Signal('Signal_US_WS_WorkZoneMarker', 'WSWZM',
           description='Work Zone Marker',
           width='0.152',
           height='0.305',
           notes='Editable speed value Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_WS_ClearSlowZoneMarker', 'WSCSZM',
           description='Clear Slow Zone Marker',
           width='0.152',
           height='0.305',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf Identified on the Red Line GX030006'),
    Signal('Signal_US_WS_Stop', 'WSS',
           description='Stop',
           width='0.762',
           height='0.762',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf Standard dimensions from MUTCD 2023 — R1-1, Table 2B-1 (PDF page 108)'),
    Signal('Signal_US_WS_ReflectiveStationStopMarker', 'WSRSSM',
           description='Reflective Station Stop Marker',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_WS_ReflectiveStationStopMarkerOperatingReverse', 'WSRSSMOR',
           description='Reflective Station Stop Marker Operating Reverse',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_WS_ReflectiveStationStopMarkerInsulatedOverlap', 'WSRSSMIO',
           description='Reflective Station Stop Marker Insulated Overlap',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_WS_HighWaterIndicator', 'WSHWI',
           description='High Water Indicator',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_WS_ResumeSpeedMarker_OneCar', 'WSRSMOC',
           description='Resume Speed Marker - One Car',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_WS_ResumeSpeedMarker_TwoCar', 'WSRSMTC',
           description='Resume Speed Marker - Two Car',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_WS_StationStopSign', 'WSSSS',
           description='Station Stop Sign',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf Identified on the Red Line GX010006'),
    Signal('Signal_US_WS_StopAndProceedSign', 'WSSAPS',
           description='Stop And Proceed Sign',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf Identified on the Red Line GX020006 and on the Grren Line GX030008'),
    Signal('Signal_US_WS_StopAndProceedSignTrack', 'WSSAPST',
           description='Stop And Proceed Sign Track',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_WS_SchoolZone', 'WSSZ',
           description='School Zone',
           width='0.609',
           height='1.219',
           notes='Editable speed value Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_WS_EndSchoolZone', 'WSESZ',
           description='End School Zone',
           width='0.609',
           height='1.219',
           notes='Editable speed value Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf'),
    Signal('Signal_US_WS_StationAudible', 'WSSA',
           description='Station Audible',
           notes='Defined in : Rulebook Operations Rules and Procedures Final for print- CR.pdf Identified on the Red Line GX010006'),
    Signal('Signal_US_WS_TrainSignalOnly', 'WSTSO',
           description='Train Signal Only',
           notes='Defined in : Videos R15-4a page 258 of the doc texas standard The text "TRAIN SIGNAL" is modifiable" Identified on the Red Line GX010003'),
    Signal('Signal_US_WS_FloodZone', 'WSFZ',
           description='Flood Zone Sign',
           notes='Identified on the Red Line GX010003 and the Green Line GX010009'),
    Signal('Signal_US_WS_SpeedPocket20', 'WSP20',
           description='Pocket 20 Sign',
           notes='Identified on the Red Line GX010006'),
    Signal('Signal_US_WS_Channelizer15', 'WSC15',
           description='Channelizer 15 Sign',
           notes='Identified on the Red Line GX010006'),
    Signal('Signal_US_WS_BlankYellowSign', 'WSBYS',
           description='Blank Yellow Sign',
           width='0.152',
           height='0.305',
           notes='Identified on the Red Line GX020003 Dimensions based on OM2-2V (6 x 12 inches) Source: Texas Standard Highway Sign Designs.pdf - Page 189 (to be confirmed for Houston)'),
    Signal('Signal_US_WS_NoTrespassing', 'WSNT',
           description='No Trespassing Sign',
           width='0.610',
           height='0.305',
           notes='Identified on the Green Line GX030009 Estimated dimensions based on R5-10c (24 x 12 inches) - To be validated Source: Texas Standard Highway Sign Designs.pdf - Page 1-97'),
    Signal('Signal_US_WS_DiagonalHazardMarker', 'WSDHM',
           description='Black and Yellow Diagonal Hazard Marker',
           width='0.305',
           height='0.914',
           notes='Identified on the Red Line GX040006 Standard reference : OM-3'),
    Signal('Signal_US_WS_NoLightRailVehicles', 'WSNLRV',
           description='No Light Rail Vehicles Sign',
           width='0.610',
           height='0.610',
           notes='Identified on the Red Line GX040006 Standard reference: R15-6 - No Motor Vehicles On Tracks Source: Texas Standard Highway Sign Designs.pdf - Page 383 (dimensions to be confirmed for Houston)'),
    Signal('Signal_US_WS_StopLookListen', 'WSSLL',
           description='Stop Look Listen Before Crossing Sign',
           width='0.457',
           height='0.762',
           notes='Identified in multiple videos on the Red Line'),
]


def read_presets() -> list[Signal]:
    if not PRESETS_FILE.exists():
        return DEFAULT_PRESETS
    try:
        records = json.loads(PRESETS_FILE.read_text(encoding='utf-8'))
        return [Signal(**item) for item in records]
    except (OSError, ValueError, TypeError) as exc:
        messagebox.showwarning('Presets', f'presets.json illisible. Presets intégrés utilisés.\n{exc}')
        return DEFAULT_PRESETS


class App(tk.Tk):
    FIELDS = [
        ('name', 'Nom technique (fichier / node)'),
        ('abbreviation', 'Abréviation XML'),
        ('description', 'Description'),
        ('family', 'Famille'),
        ('width', 'Largeur (m)'),
        ('height', 'Hauteur (m)'),
        ('depth', 'Profondeur (m)'),
        ('notes', 'Notes internes (non exportées)'),
    ]

    def __init__(self):
        super().__init__()
        self.title('Houston — XML Feature Generator')
        self.geometry('870x740')
        self.minsize(750, 610)
        self.presets = read_presets()
        self.variables = {k: tk.StringVar(self) for k, _ in self.FIELDS}
        self.selected = tk.StringVar(self)
        self.setup_ui()
        if self.presets:
            self.selected.set(self.presets[0].name)
            self.on_preset()
        for v in self.variables.values():
            v.trace_add('write', lambda *_: self.refresh_preview())

    def setup_ui(self):
        main = ttk.Frame(self, padding=14)
        main.pack(fill='both', expand=True)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(12, weight=1)
        ttk.Label(main, text='Houston METRORail — Générateur de feature_type XML',
                  font=('Segoe UI', 14, 'bold')).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 8))
        ttk.Label(main, text='Modèle :').grid(row=1, column=0, sticky='w', pady=4)
        self.combo = ttk.Combobox(main, textvariable=self.selected, state='readonly',
                                  values=[s.name for s in self.presets], width=52)
        self.combo.grid(row=1, column=1, sticky='ew', pady=4)
        self.combo.bind('<<ComboboxSelected>>', lambda _: self.on_preset())
        ttk.Button(main, text='Nouveau', command=self.new_signal).grid(row=1, column=2, padx=(8, 0))
        for index, (key, label) in enumerate(self.FIELDS, start=2):
            ttk.Label(main, text=label).grid(row=index, column=0, sticky='w', pady=3)
            ttk.Entry(main, textvariable=self.variables[key]).grid(row=index, column=1, columnspan=2,
                                                                       sticky='ew', pady=3)
        ttk.Label(main, text='Les valeurs x.x sont acceptées. Les dimensions sont toujours en mètres dans le XML.',
                  foreground='#6a5b1b').grid(row=10, column=0, columnspan=3, sticky='w', pady=(5, 8))
        buttons = ttk.Frame(main)
        buttons.grid(row=11, column=0, columnspan=3, sticky='ew', pady=(0, 8))
        ttk.Button(buttons, text='Importer une ligne HTML', command=self.import_html).pack(side='left', padx=(0, 6))
        ttk.Button(buttons, text='Enregistrer preset', command=self.save_preset).pack(side='left', padx=6)
        ttk.Button(buttons, text='Générer XML…', command=self.export).pack(side='left', padx=6)
        ttk.Button(buttons, text='Générer tous les presets…', command=self.export_all).pack(side='left', padx=6)
        preview_frame = ttk.LabelFrame(main, text='Aperçu XML (non sauvegardé)')
        preview_frame.grid(row=12, column=0, columnspan=3, sticky='nsew')
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        self.preview = tk.Text(preview_frame, wrap='none', font=('Consolas', 9), padx=8, pady=8)
        self.preview.grid(row=0, column=0, sticky='nsew')
        yscroll = ttk.Scrollbar(preview_frame, orient='vertical', command=self.preview.yview)
        yscroll.grid(row=0, column=1, sticky='ns')
        xscroll = ttk.Scrollbar(preview_frame, orient='horizontal', command=self.preview.xview)
        xscroll.grid(row=1, column=0, sticky='ew')
        self.preview.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.status = tk.StringVar(value='Prêt.')
        ttk.Label(main, textvariable=self.status).grid(row=13, column=0, columnspan=3, sticky='w', pady=(6, 0))

    def fill(self, signal: Signal):
        for k, var in self.variables.items():
            var.set(str(getattr(signal, k)))
        self.refresh_preview()

    def current(self) -> Signal:
        return Signal(**{k: v.get().strip() for k, v in self.variables.items()})

    def on_preset(self):
        match = next((x for x in self.presets if x.name == self.selected.get()), None)
        if match:
            self.fill(match)

    def new_signal(self):
        self.selected.set('')
        self.fill(Signal())

    def refresh_preview(self):
        if not hasattr(self, 'preview'):
            return
        try:
            xml = build_xml(self.current())
            self.status.set('Prêt — XML valide syntaxiquement (compatibilité projet à vérifier).')
        except ValueError as ex:
            xml = f'Erreur de saisie : {ex}'
            self.status.set('Corriger les champs avant export.')
        self.preview.configure(state='normal')
        self.preview.delete('1.0', 'end')
        self.preview.insert('1.0', xml)
        self.preview.configure(state='disabled')

    def save_preset(self):
        try:
            sig = self.current()
            build_xml(sig)
            i = next((i for i, x in enumerate(self.presets) if x.name == sig.name), None)
            if i is None:
                self.presets.append(sig)
            else:
                self.presets[i] = sig
            PRESETS_FILE.write_text(json.dumps([asdict(x) for x in self.presets], ensure_ascii=False,
                                               indent=2) + '\n', encoding='utf-8')
            self.combo['values'] = [x.name for x in self.presets]
            self.selected.set(sig.name)
            self.status.set('Preset enregistré dans presets.json.')
        except (ValueError, OSError) as ex:
            messagebox.showerror('Preset', str(ex))

    def export(self):
        try:
            sig = self.current()
            xml = build_xml(sig)
        except ValueError as ex:
            messagebox.showerror('XML invalide', str(ex))
            return
        filename = filedialog.asksaveasfilename(title='Enregistrer feature_type XML',
                    defaultextension='.xml', initialfile=sig.name + '.xml',
                    filetypes=[('XML', '*.xml')])
        if not filename:
            return
        try:
            Path(filename).write_text(xml, encoding='utf-8')
        except OSError as ex:
            messagebox.showerror('Écriture impossible', str(ex))
            return
        self.status.set(f'Créé : {filename}')
        messagebox.showinfo('Terminé', f'XML créé :\n{filename}\n\nLes PNG et le .node ne sont pas créés automatiquement.')

    def export_all(self):
        folder = filedialog.askdirectory(title='Dossier de sortie de tous les XML')
        if not folder:
            return
        dest = Path(folder)
        existing = [s.name for s in self.presets if (dest / (s.name + '.xml')).exists()]
        if existing and not messagebox.askyesno('Écrasement',
              f'{len(existing)} fichier(s) XML existe(nt) déjà. Les écraser ?'):
            return
        try:
            for sig in self.presets:
                xml = build_xml(sig)
                (dest / (sig.name + '.xml')).write_text(xml, encoding='utf-8')
        except (ValueError, OSError) as ex:
            messagebox.showerror('Export interrompu', str(ex))
            return
        self.status.set(f'{len(self.presets)} XML enregistrés dans {dest}')
        messagebox.showinfo('Terminé', f'{len(self.presets)} XML exportés.\nDossier : {dest}')

    def import_html(self):
        dialog = tk.Toplevel(self)
        dialog.title('Importer une ligne du tableau HTML')
        dialog.geometry('760x350')
        dialog.transient(self)
        dialog.grab_set()
        ttk.Label(dialog, text='Colle une ligne complète <tr> ... </tr> puis clique sur Importer.',
                  padding=(10, 10)).pack(anchor='w')
        txt = tk.Text(dialog, wrap='word', font=('Consolas', 10))
        txt.pack(fill='both', expand=True, padx=10)
        def do_import():
            try:
                sig = parse_html_row(txt.get('1.0', 'end'))
            except ValueError as ex:
                messagebox.showerror('Import HTML', str(ex), parent=dialog)
                return
            self.selected.set('')
            self.fill(sig)
            dialog.destroy()
            self.status.set('Ligne HTML importée — vérifie les données puis génère le XML.')
        ttk.Button(dialog, text='Importer', command=do_import).pack(anchor='e', padx=10, pady=10)


if __name__ == '__main__':
    App().mainloop()
