# Changelog

_For the English version please see the release section of Github._

## v1.0.0 – First stable release

Woho!


## v1.1.0 – Cover, filename and more

Bei der Einreichung können nun Cover angehängt werden, Dateien werden automatisch richtig benannt und eine Reihe von Quality-of-life Verbesserungen:

- Produzierende können nun ihrer Sendung optional auch ein Coverfoto beifügen. Unterstützt werden aktuell `.jpg .jpeg .png`. Gespeichert wird das Cover in der Spalte `Cover` in der Tabelle `Episoden`.
- Währen eines laufenden Uploads ist es nun nicht mehr möglich, das Browserfenster einfach zu schließen. Nutzende müssen bestätigen, dass sie dies wirklich tun möchten.
- Der Name von Dateien (Audio, Waveform und Cover) beinhalten nun automatisch _Id, Erstsendedatum und Formatname._ Um eine korrekt benannte Datei runterladen zu können, muss in Noco zunächst in der Datei-Zelle auf das Vergrößern-Icon geklickt werden und dann der Downloadbutton verwendet werden. 
- Während des Uploads wird nun der User darauf hingewiesen, dass das die Seite nicht geschlossen werden darf.
- Die Spalten `Status Waveform` und `Status Optimierung` zeigen nun die korrekten Stati für die Prozesse an.
- Wenn die Applikation im Testmodus läuft, wird dies in Zukunft in den Mailbetreffen ersichtlich. Dem Mailbetreff ist in diesem Fall jeweils ein `[Test]` torangefügt. 


## v1.2.0 – Fully automatic optimisation of audio files

Eingegangene Audiodateien werden nun nach dem Upload automatisiert analysiert und nach unseren Anforderungen optimiert. Dies umfasst folgende Punkte:

- Stille zu Beginn des Files wird erkannt und entfernt.
- Stille am Ende des Files wird erkannt und entfernt.
- Stille innerhalb des Files wird erkannt und in der NocoDB-Tabelle vermerkt.
- Der Dateiname wird in das Titelfeld der Metadaten geschrieben (dies ist notwendig, da mAirList die Datei sonst nicht lesen kann).
- Der `loudnorm` Filter wendet den EBU R128 Algorithmus an.
- Die Datei wird als mp3 mit den konfigurierten Bit- und Samplerate kodiert.
- Festgestellte Probleme sowie die Dauer der optimierten Datei werden im `Log Optimierung` Feld in NocoDB für jede Episode gespeichert.


Weitere Änderungen:

- Seitenfuss mit der Versionsangabe und Links zu Impressum sowie Datenschutzangaben.
- Migration auf das CLI Framework Typer.


## v1.2.1 – Filenames and metadata in optimized files

- The file names now follow the new schemas as decided by the company.
- The optimized files now contain additional information in the mp3 meta tags.


## v.2.2 – To be named

- Fixed typo in internal e-mail message.
- Updated content of help page.
- Updated form with more detailed texts.
- The icons in the upload form are now more fitting.
- Description is now an optional field in the upload form.
- Test data in upload form is now a little bit more meaningful.
- Form now presents user with a meaningful default title based on selected show and air-date.