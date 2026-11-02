#!/usr/bin/env python3
"""Houston XML pipeline: HTML catalog -> feature_type XML -> configuration Signs layer.
Python >=3.9; standard library only. Does NOT overwrite differing existing XML.
"""
from __future__ import annotations

import difflib
import codecs
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
import re
import hashlib
import shutil
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import xml.etree.ElementTree as ET

from houston_xml_generator import Signal, build_xml, parse_html_row

SIGNAL_RE = re.compile(r'^Signal_US_WS_[A-Za-z0-9_]+$')
LAYER_RE = re.compile(r'(<layer\s+id=["\']351["\']\s+name=["\']Signs["\']\s*>)(.*?)(</layer>)', re.S)
ENTRY_RE = re.compile(r'<feature_type_layer\s+feature_type=["\']([^"\']+)["\']')

def decode_text_file(path: Path, *, is_html: bool = False):
    """Decode Windows HTML/XML inputs without discarding BOM or changing original files.

    Returns (text, encoding_for_round_trip). Unknown encodings fail closed.
    """
    raw = path.read_bytes()
    if raw.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        return raw.decode('utf-32'), 'utf-32'
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return raw.decode('utf-16'), 'utf-16'
    if raw.startswith(codecs.BOM_UTF8):
        return raw.decode('utf-8-sig'), 'utf-8-sig'
    if raw[:4] in (b'\x00<\x00?', b'\x00<\x00c'):
        return raw.decode('utf-16-be'), 'utf-16-be'
    if raw[:4] in (b'<\x00?\x00', b'<\x00c\x00'):
        return raw.decode('utf-16-le'), 'utf-16-le'
    # Explicit encoding declarations (XML or HTML) take precedence.
    head = raw[:512].decode('ascii', errors='ignore')
    declared = re.search(r'(?:encoding\s*=\s*["\']([^"\']+)["\']|charset\s*=\s*["\']?([\w.-]+))', head, re.I)
    encoding = (declared.group(1) or declared.group(2)) if declared else 'utf-8'
    try:
        return raw.decode(encoding), encoding
    except (UnicodeError, LookupError) as e:
        if is_html and not declared:
            # HTML exported by legacy Windows tools is often Windows-1252.
            return raw.decode('cp1252'), 'cp1252'
        raise ValueError(f'Encodage non pris en charge pour {path.name} ({encoding}) : {e}') from e


class RowExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.level = 0
        self.row = []
        self.rows = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'tr':
            self.level += 1
            if self.level == 1:
                self.row = ['<tr>']
            else:
                self.row.append(self.get_starttag_text())
        elif self.level:
            self.row.append(self.get_starttag_text())
    def handle_startendtag(self, tag, attrs):
        if self.level:
            self.row.append(self.get_starttag_text())
    def handle_endtag(self, tag):
        if self.level:
            self.row.append(f'</{tag}>')
            if tag.lower() == 'tr':
                self.level -= 1
                if not self.level:
                    self.rows.append(''.join(self.row))
    def handle_data(self, data):
        if self.level:
            self.row.append(data)
    def handle_entityref(self, name):
        if self.level:
            self.row.append(f'&{name};')
    def handle_charref(self, name):
        if self.level:
            self.row.append(f'&#{name};')

def load_catalog(path: Path):
    html, _ = decode_text_file(path, is_html=True)
    p = RowExtractor()
    p.feed(html)
    signals, errors = {}, []
    for n, row in enumerate(p.rows, 1):
        if not re.search(r'Signal_US_WS_[A-Za-z0-9_]+', row):
            continue
        try:
            sig = parse_html_row(row)
            if not SIGNAL_RE.fullmatch(sig.name):
                raise ValueError('nom de signal invalide')
            if sig.name in signals:
                raise ValueError('nom présent plusieurs fois dans le HTML')
            signals[sig.name] = sig
        except ValueError as ex:
            errors.append(f'Ligne HTML {n}: {ex}')
    if not signals:
        errors.append('Aucun Signal_US_WS_* reconnu dans le catalogue HTML.')
    return signals, errors

def read_config(path: Path):
    text, enc = decode_text_file(path)
    root = ET.fromstring(text)
    if root.tag != 'config':
        raise ValueError('Le fichier XML doit avoir une racine <config>.')
    layers = root.findall(".//layer[@id='351'][@name='Signs']")
    if len(layers) != 1:
        raise ValueError('La couche id=351 / Signs est absente ou dupliquée.')
    found = list(LAYER_RE.finditer(text))
    if len(found) != 1:
        raise ValueError('Impossible de localiser sans ambiguïté le texte de la couche Signs.')
    actual = {e.get('feature_type') for e in layers[0].findall('feature_type_layer')}
    regex_actual = set(ENTRY_RE.findall(found[0].group(2)))
    if actual != regex_actual:
        raise ValueError('La couche Signs comporte une structure non standard: modification annulée.')
    return text, enc, actual, found[0]

def planned_change(signals, out_dir: Path, config_path: Path):
    """Fail-closed: all differences flagged, not overwritten."""
    old, enc, registered, match = read_config(config_path)
    create, identical, conflicts, additions = [], [], [], []
    for name, sig in sorted(signals.items()):
        new_xml = build_xml(sig)
        out = out_dir / (name + '.xml')
        if out.exists():
            try:
                current, _ = decode_text_file(out)
            except UnicodeError:
                conflicts.append(f'{name}: XML existant non décodable')
                continue
            try:
                a = ET.fromstring(current)
                b = ET.fromstring(new_xml)
                # Ignore whitespace-only text nodes and attribute ordering.
                def canon(e):
                    return (e.tag, tuple(sorted(e.attrib.items())), (e.text or '').strip(),
                            tuple(canon(c) for c in e))
                if canon(a) == canon(b):
                    identical.append(name)
                else:
                    conflicts.append(f'{name}: XML existant différent (conservé, non écrasé)')
            except ET.ParseError:
                conflicts.append(f'{name}: XML existant invalide (conservé)')
        else:
            create.append((name, out, new_xml))
        if name not in registered:
            additions.append(name)
    # Register only names that are already XML valid or will be created.
    valid_names = set(identical) | {name for name, _, _ in create}
    additions = [name for name in additions if name in valid_names]
    newline = '\r\n' if '\r\n' in old else '\n'
    indent = '\t\t\t\t' if '\t' in match.group(2) else '                '
    insert = ''.join(f'{newline}{indent}<feature_type_layer feature_type="{name}" display_name="{name}" />' for name in additions)
    # insert just before closing tag with appropriate whitespace
    middle = match.group(2)
    trailing = re.search(r'([ \t]*\r?\n[ \t]*)$', middle)
    pos = trailing.start() if trailing else len(middle)
    updated_mid = middle[:pos] + insert + middle[pos:]
    updated = old[:match.start(2)] + updated_mid + old[match.end(2):]
    if updated != old:
        ET.fromstring(updated)
        _, _, new_registered, _ = read_config_text(updated)
        if not set(additions).issubset(new_registered):
            raise ValueError('Validation des ajouts échouée, aucune modification réalisée.')
    return dict(old=old, updated=updated, encoding=enc, source_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(), creates=create, identical=identical,
                conflicts=conflicts, additions=additions)

def read_config_text(text):
    root = ET.fromstring(text)
    layers = root.findall(".//layer[@id='351'][@name='Signs']")
    if len(layers) != 1:
        raise ValueError('Couche Signs introuvable après modification')
    m = list(LAYER_RE.finditer(text))
    if len(m) != 1:
        raise ValueError('Couche Signs ambiguë après modification')
    return text, 'utf-8', {e.get('feature_type') for e in layers[0].findall('feature_type_layer')}, m[0]

def apply_plan(plan, config_path: Path):
    """Write new files then replace config. Backup before edits, restore on error."""
    if plan['conflicts']:
        raise ValueError('Il existe des conflits. Aucun fichier ne sera modifié.\n' + '\n'.join(plan['conflicts']))
    if hashlib.sha256(config_path.read_bytes()).hexdigest() != plan['source_sha256']:
        raise ValueError('Le fichier layers.xml a changé depuis l’analyse. Relance l’aperçu avant de générer.')
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    created = []
    backup = None
    try:
        if plan['old'] != plan['updated']:
            backup = config_path.with_name(config_path.name + '.' + stamp + '.bak')
            shutil.copy2(config_path, backup)
        for name, out, contents in plan['creates']:
            # Exclusive create: never overwrite a concurrent or pre-existing file.
            with out.open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(contents)
            created.append(out)
        if backup:
            fd, tmp = tempfile.mkstemp(prefix='.houston_', suffix='.tmp', dir=config_path.parent)
            import os
            try:
                with os.fdopen(fd, 'w', encoding=plan['encoding'], newline='') as f:
                    f.write(plan['updated'])
                os.replace(tmp, config_path)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
    except Exception:
        if backup and backup.exists():
            shutil.copy2(backup, config_path)
        for out in created:
            out.unlink(missing_ok=True)
        raise
    return backup

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Houston — HTML → XML → Layers (sans écrasement)')
        self.geometry('970x730')
        self.minsize(800, 600)
        self.html_path = tk.StringVar()
        self.out_path = tk.StringVar()
        self.config_path = tk.StringVar()
        self.plan = None
        self.layout()

    def layout(self):
        wrap = ttk.Frame(self, padding=14)
        wrap.pack(fill='both', expand=True)
        wrap.columnconfigure(1, weight=1)
        wrap.rowconfigure(5, weight=1)
        ttk.Label(wrap, text='Houston — Automatisation des pancartes XML',
                  font=('Segoe UI', 15, 'bold')).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 12))
        lines = [('1. Catalogue HTML (source)', self.html_path, self.choose_html),
                 ('2. Dossier des feature_type XML', self.out_path, self.choose_out),
                 ('3. Fichier config des layers', self.config_path, self.choose_config)]
        for i, (label, var, cmd) in enumerate(lines, 1):
            ttk.Label(wrap, text=label).grid(row=i, column=0, sticky='w', pady=8)
            ttk.Entry(wrap, textvariable=var).grid(row=i, column=1, sticky='ew', padx=10)
            ttk.Button(wrap, text='Parcourir…', command=cmd).grid(row=i, column=2)
            var.trace_add('write', lambda *_: self.invalidate())
        bar = ttk.Frame(wrap)
        bar.grid(row=4, column=0, columnspan=3, sticky='ew', pady=(8, 14))
        ttk.Button(bar, text='1. Analyser / Aperçu des modifications', command=self.preview).pack(side='left', padx=(0, 10))
        self.apply_btn = ttk.Button(bar, text='2. Générer et synchroniser', command=self.apply, state='disabled')
        self.apply_btn.pack(side='left')
        ttk.Label(bar, text='Aucune donnée existante ne sera écrasée.', foreground='#216a34').pack(side='right')
        output = ttk.LabelFrame(wrap, text='Rapport avant modification')
        output.grid(row=5, column=0, columnspan=3, sticky='nsew')
        output.columnconfigure(0, weight=1)
        output.rowconfigure(0, weight=1)
        self.report = tk.Text(output, wrap='none', font=('Consolas', 10))
        self.report.grid(row=0, column=0, sticky='nsew')
        ys = ttk.Scrollbar(output, orient='vertical', command=self.report.yview)
        ys.grid(row=0, column=1, sticky='ns')
        xs = ttk.Scrollbar(output, orient='horizontal', command=self.report.xview)
        xs.grid(row=1, column=0, sticky='ew')
        self.report.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ttk.Label(wrap, text='Conserve le HTML original. Sauvegarde .bak automatique de la config. SVN : vérifier diff puis commit.',
                  foreground='#66551b').grid(row=6, column=0, columnspan=3, sticky='w', pady=(12, 0))

    def invalidate(self):
        self.plan = None
        if hasattr(self, 'apply_btn'):
            self.apply_btn.configure(state='disabled')
    def choose_html(self):
        x = filedialog.askopenfilename(filetypes=[('HTML','*.html *.htm'),('Tous fichiers','*.*')])
        if x: self.html_path.set(x)
    def choose_out(self):
        x = filedialog.askdirectory()
        if x: self.out_path.set(x)
    def choose_config(self):
        x = filedialog.askopenfilename(filetypes=[('XML','*.xml'),('Tous fichiers','*.*')])
        if x: self.config_path.set(x)
    def set_report(self, content):
        self.report.delete('1.0', 'end')
        self.report.insert('1.0', content)
    def preview(self):
        try:
            source, target, config = Path(self.html_path.get()), Path(self.out_path.get()), Path(self.config_path.get())
            if not source.is_file() or not target.is_dir() or not config.is_file():
                raise ValueError('Sélectionne un catalogue HTML, un dossier XML existant et un fichier config XML.')
            signals, errors = load_catalog(source)
            if errors:
                raise ValueError('Erreurs du HTML — rien ne sera modifié :\n' + '\n'.join(errors))
            self.plan = planned_change(signals, target, config)
            p = self.plan
            lines = [f'Signaux du HTML : {len(signals)}',
                     f'Nouveaux XML à créer : {len(p["creates"])}',
                     f'XML déjà identiques : {len(p["identical"])}',
                     f'Entrées à ajouter dans Signs (layer 351) : {len(p["additions"])}',
                     f'Conflits : {len(p["conflicts"])}', '',
                     'NOUVEAUX XML :'] + ['  + ' + x[0] + '.xml' for x in p['creates']]
            lines += ['', 'AJOUTS CONFIG SIGNS :'] + ['  + ' + x for x in p['additions']]
            lines += ['', 'DÉJÀ IDENTIQUES :'] + ['  = ' + x for x in p['identical']]
            lines += ['', 'CONFLITS BLOQUANTS :'] + ['  ! ' + x for x in p['conflicts']]
            lines += ['', 'DIFF CONFIG (ajouts uniquement) :']
            lines += list(difflib.unified_diff(p['old'].splitlines(), p['updated'].splitlines(),
                         fromfile='config originale', tofile='config proposée', lineterm=''))
            self.set_report('\n'.join(lines))
            self.apply_btn.configure(state='normal' if not p['conflicts'] and (p['creates'] or p['additions']) else 'disabled')
        except (OSError, UnicodeError, ValueError, ET.ParseError) as ex:
            self.invalidate()
            self.set_report('ERREUR — aucune modification réalisée :\n' + str(ex))

    def apply(self):
        if not self.plan:
            return
        if not messagebox.askyesno('Confirmer', 'Créer les nouveaux XML et mettre à jour la couche Signs ?\n\nUne copie .bak de la config sera conservée.'):
            return
        try:
            b = apply_plan(self.plan, Path(self.config_path.get()))
            messagebox.showinfo('Succès', f'{len(self.plan["creates"])} XML créés.\n{len(self.plan["additions"])} références ajoutées.\nBackup : {b or "aucun changement config"}\n\nVérifier SVN diff avant commit.')
            self.invalidate()
            self.preview()
        except (OSError, ValueError) as ex:
            messagebox.showerror('Erreur', f'Opération annulée / tentative de restauration :\n{ex}')
            self.invalidate()

if __name__ == '__main__':
    App().mainloop()
