# Varuna Fahrwasser

Pegelstände und mögliche Abladetiefen auf der Strecke der GMS Varuna,
dazu die Niederschlagsprognose im Einzugsgebiet.

Die Seite ist eine einzelne HTML-Datei. Die Zahlen stehen in `daten.json`,
die jeden Morgen automatisch neu geschrieben wird.

## Was wo liegt

| Datei | Zweck |
|---|---|
| `index.html` | Das Dashboard. Enthält Gestaltung und Rechenlogik, lädt beim Öffnen `daten.json`. |
| `daten.json` | Die aktuellen Werte. Wird vom Skript überschrieben, nicht von Hand pflegen. |
| `scripts/update.py` | Holt Pegel und Regen und schreibt `daten.json`. Ohne Zugangsdaten, beide Quellen sind offen. |
| `.github/workflows/update.yml` | Der Zeitplan: ruft das Skript täglich auf und lädt das Ergebnis hoch. |

## Einrichtung

1. Neues Repository anlegen, Sichtbarkeit **Public** (nötig, damit GitHub Pages
   ohne Bezahlkonto funktioniert).
2. Diese Dateien hochladen — der Ordneraufbau muss erhalten bleiben.
3. Unter **Settings → Pages** als Quelle `Deploy from a branch`, Branch `main`,
   Ordner `/ (root)` wählen. Nach ein bis zwei Minuten ist die Seite unter
   `https://<benutzername>.github.io/<repository>/` erreichbar.
4. Unter **Settings → Actions → General** bei *Workflow permissions*
   **Read and write permissions** einschalten. Ohne das darf der Zeitplan
   `daten.json` nicht zurückschreiben.
5. Unter **Actions** den Ablauf *Pegel und Regen aktualisieren* auswählen und
   einmal **Run workflow** drücken. Läuft er durch, ist alles richtig
   eingerichtet.

## Die Rechnung hinter der Abladetiefe

Abladetiefe = Pegelstand plus fester Zuschlag:

- Maxau − 160 cm
- Mannheim + 70 cm
- Mainz + 30 cm

Diese Zuschläge stehen in `index.html` in der Zeile `var OFFSET_CM`.
Wer sie ändert, ändert damit alle angezeigten Abladetiefen.

## Zeitplan

Der Ablauf startet um 03:40 und 04:40 UTC. Damit wird der 05:00-Wert
Ortszeit sowohl in der Sommer- als auch in der Winterzeit erwischt; der
jeweils zweite Lauf schreibt denselben Wert nur erneut.

## Quellen

- Pegelstände: [PEGELONLINE](https://www.pegelonline.wsv.de/) der
  Wasserstraßen- und Schifffahrtsverwaltung des Bundes. Ungeprüfte Rohdaten.
- Niederschlag: [MET Norway](https://api.met.no/), Lizenz CC BY 4.0.
  Deren Nutzungsbedingungen verlangen eine Kennung mit Kontaktadresse im
  Abruf — sie steht in `scripts/update.py` unter `USER_AGENT`.
