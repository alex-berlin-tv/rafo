<p align="center" height="100px">
  <img src="misc/logo.png" />
</p>

# rafo

rafo aka "radio form" is a small application that allows external producers to submit the audio file and metadata of their radio programmes via a web form. NocoDB is used as the backend. Developed by ALEX Berlin as part of ALEX Digital 2023.

## Installation

Make sure that Python and pip are installed in a relatively new version. Then download the code with git.

```
git clone https://github.com/alex-berlin-tv/rafo.git
```

Secret settings are stored in the `.secrets.toml` file. To create these:

```
mv secrets.tpl.toml .secrets.toml
```

Then adapt the contents of the file to your requirements.

All other settings can be found in the `settings.toml` file, which you can also adjust according to your needs.

After that, the application can be installed.

```
python -m venv .venv
source .venv/bin/activate
pip install .
```

Start rafo with:

```
rafo run
```

Translated with www.DeepL.com/Translator (free version)


## Configuration of NocoDB

rafo uses the application NocoDB as a backend for the data. For this to work correctly, the following structures must be created:

- Radioupload (Project)
    - Produzenten (Table)
        - Ident (`Formula` Field): `CONCAT("p", {Id}, "-", LEFT({Vorname}, 2), LEFT({Name}, 2))`
        - Vorname (`SingleLineText` Field)
        - Nachname (`SingleLineText` Field)
        - Email (`Email` Field)
        - UUID (`SingleLineText` Field)
    - Formate (Table)
        - Name (`SingleLineText` Field)
        - Ident (`Formula` Field): `CONCAT("s-", {Id})`
        - UUID (`SingleLineText` Field)
        - Produzent (`LinkToAnotherRecord` Field): Produzenten
        - Description (`LongText` Field)
    - Episoden (Table)
        - Titel (`SingleLineText` Field)
        - Eingereicht von (`LinkToAnotherRecord` Field): Produzenten
        - Format (`LinkToAnotherRecord` Field): Formate
        - Waveform (`Attachment` Field)
        - Beschreibung (`LongText` Field)
        - Waveform (`Attachment` Field)
        - Quelldatei (`Attachment` Field)
        - Optimierte Datei (`Attachment` Field)
        - Manuelle Datei (`Attachment` Field)
        - Status Waveform (`SingleSelect` Field): Pending / Läuft / Fertig / Abgebrochen
        - Status Optimierung (`SingleSelect` Field): Pending / Läuft / Fertig / Abgebrochen
        - Status Omnia (`SingleSelect` Field): Nicht auf Omnia / STARTE Upload zu Omnia / Liegt auf Omnia bereit / VERÖFFENTLICHEN / Online in der Mediathek