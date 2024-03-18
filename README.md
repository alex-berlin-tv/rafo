<p align="center">
  <img src="misc/logo.svg" height="150"/>
</p>

# rafo

rafo aka "radio form" is a small application that allows external producers to submit the audio file and metadata of their radio programmes via a web form. [Baserow](https://baserow.io/) is used as the backend. Developed by [ALEX Berlin](https://www.alex-berlin.de/) as part of ALEX Digital 2023.

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

## Configuration of Baserow

rafo uses the application [Baserow](https://baserow.io/) as a backend for the data. For this to work correctly, the following structures must be created:

### Tables

- Person (Table)
    - Name : Text
	- Typ: `Single Select`
        - Intern
        - Alumni
        - Extern
        - Test
	- E-Mail: `Email`
	- Telefon: `Text`
	- Upload Form: `Function`
	- Status Upload Form: `Single Select`
        - Aktiviert
        - Deaktiviert
	- Upload Link erhalten?: `Bool`
	- UUID: `UUID`
	- Legacy UUID: `Text`

- Format (Table)
	- Name: `Text`
	- Verantwortlich: `Relationship[Person, n:n]`
	- Herkunft: `Single Select`
        - Intern
        - AMW
        - Extern
        - Test
	- Medium: `Single Select`
        - TV
        - Radio
        - Podcast
	- Beschreibung: `Long Text`
	- Cover: `File`
	- URL: `Long Text`
	- Betreuung: `Relationship[Person, n:n]`
- Upload (Table)
	- Name: `Text`
	- Geplante Ausstrahlung: `Datetime`
	- Beschreibung: `Long Text`
	- Kommentar Produzent: `Long Text`
	- Format: `Relationship[Format, 1:n]`
	- Eingereicht von: `Relationship[Person, 1:n]`
	- Episode: `Relationship[Episode, 1:n]`
	- Waveform: `File`
	- Quelldatei: `File`
	- Optimierte Datei: `File`
	- Manuelle Datei: `File`
	- Cover: `File`
	- Dauer: `Duration`
    - Status: `Multiple Select`
        - Waveform: Ausstehend
        - Waveform: Läuft
        - Waveform: Fertig
        - Waveform: Fehler
        - Optimierung: Ausstehend
        - Optimierung: Läuft
        - Optimierung: Fertig
        - Optimierung: Fertig, Log beachten!
        - Optimierung: Fehler
        - Omnia: Nicht auf Omnia
        - Omnia: Upload läuft
        - Omnia: Liegt auf Omnia
        - Omnia: Fehler während Upload
        - Intern: Legacy URL benutzt
        - Intern: NocoDB Import
	- Log Optimierung: `Long Text`
	- Upload Omnia (Button): `Formula`
	- Hochgeladen am: `Datetime`
	- UUID: `UUID`