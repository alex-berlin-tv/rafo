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


## v1.2.2 – Frontend improvements

- Fixed typo in internal e-mail message.
- Updated content of help page.
- Updated form with more detailed help texts.
- The icons in the upload form are now more fitting.
- Description is now an optional field in the upload form.
- Test data in upload form is now a little bit more meaningful.
- Form now presents user with a meaningful default title based on selected show and air-date.
- Broadcasting date can not be more than 24h in the past.


## v1.3.0 – Backend migrated to Baserow and further improvements

With this version, Baserow replaces NocoDB as the backend of the software. This is the basis for the further migration of our broadcast planning to Baserow. Furthermore, Baserow currently offers a better range of functions and stability of the API than NocoDB. The backend is now accessed via a Pydantic model. This means that the structure of the Baserow tables is always automatically validated. In addition, various changes and optimizations have been made to the data model based on the experience gained in recent months.

In addition, a number of changes and optimisations have been made:

- The upload model now caches the linked format and uploader centrally. This reduces the required calls to the backend per upload. Especially in the mail module.
- The states of an upload are now saved as multiselect.
- The duration of an upload is written to a dedicated duration field after optimisation. This means that the duration is available in the backend in a machine-readable format.
- The upload form can now be activated per person. This makes it possible to create people in the backend without them being able to use the upload form. This is particularly important as the backend will also be responsible for managing TV content in future, but TV producers should not be able to use the upload form.
- Supervisors can now be defined for a show. They receive a confirmation email after uploading this show.
- Confirmation emails now use the HTML list tag for rendering.
- The templates for the confirmation mails have been updated and their variables have been adapted to reflect the changes in the data model.
- Implementation of a migration process for legacy UUIDs at personen. As the switch to Baserow and its native UUID field means that the existing UUIDs cannot be transferred from noco, there are new URLs for all producers. To make the transition phase as simple as possible, a grace phase has been implemented in which the old URL can still be used. In this case, however, users are informed several times (in the form as well as in the emails) that they should use the new URL. After the grace period has expired, the new URL must be used.
- New logo.