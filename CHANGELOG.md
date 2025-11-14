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
- Internal Mails now state the current version of the software.

## v1.4.0 – All Calls Async, Omnia Export, UI Enhancements, API Client Refactoring, Podcasts

This release introduces advancements across various areas. The highlight is the fully automated export of Upload entries from Baserow to Omnia, including metadata and publication timelines. To achieve this, it was necessary to make all aspects of the software (especially API calls to Omnia and Baserow) asynchronous. In this process, initial divergent processes for podcasts were also implemented. Additionally, the structure of Single and Multiple Selects in the Baserow Abstraction Layer was refactored. Now, Single and Multiple Selects Fields are always tied to an Enum. Moreover, various minor tweaks were made to the Upload UI, along with several bug fixes.

Detailed Changes:

- Asynchronous Operations: All requests to both Baserow and Omnia are now asynchronous.
- Omnia Export:
    - An Upload entry from Baserow can now be exported to Omnia with a single button press.
    - The progress of each step is displayed to the user on a dynamic page that updates through Server Sent Events. Errors and warnings are highlighted in color. Each notification can contain a series of additional information in a Key-Value format, displayed as a list. The page automatically scrolls to the latest notification. Progress is also shown in a progress bar.
    - Loads data from Baserow.
    - Loads information about the linked show from Omnia. (This feature might be removed in the future).
    - Media file is exported to Omnia.
    - Reference Number Check: Users are warned if there is already content on Omnia with the reference number of the Upload being exported.
    - The following metadata are set in Omnia: Description, Reference Number, First Air Date, Publication and Depublication Date. If the Upload lacks a custom description, the description of the show linked in Baserow is used.
    - Media file is linked with the appropriate show.
    - In the config of rafo, a list of Omnia Show IDs can be defined in `shows_for_all_upload_exports`. A media file will always be linked with these shows as well.
    - The cover is uploaded to Omnia and linked with the media content. If the Upload does not have a specific cover, the default cover of the show stored in Baserow is used.
    - The Baserow entry of the Upload is updated with the Omnia ID of the exported item.
    - All set metadata are validated to ensure that the entry on Omnia correctly has all metadata set.
    - Upon completion of the export, users can copy the Omnia ID of the entry to their clipboard by clicking a button.
- Refactoring of Single and Multiple Select Fields:
    - The data type of the entries of the select fields is now unified.
    - The entry fields are bound to an Enum that contains the possible values.
- UI – Tweaks and Bug Fixes:
    - General: The footer now correctly sticks to the bottom of the page in every situation.
    - Logo: The logo is now simpler and scales better at smaller sizes.
    - Upload View: The description field is now labeled as "public description."
    - Upload View: The comment field has been renamed to "message to the broadcasting team."
    - Upload View: The requirement for the description field has been removed.
- Podcasts: Podcasts sometimes require different processes for Upload and export to Omnia. The first steps have now been implemented.
    - If a user selects a show configured as a Podcast in Baserow (Medium) during Upload, a warning is displayed that the user must handle music rights clearance themselves.
    - If a user selects a Podcast show for Upload, the date field is labeled as "Publication Date."
    - When an Upload, whose linked show is marked as a Podcast, is exported to Omnia, no Depublication Date is set.


## v1.4.1 – Timezone bug fixed

Previously, the release date specified in the upload form was transmitted to Baserow in UTC time. As a result, the time entries in the Baserow table were incorrect. The time zone transmitted to Baserow can now be edited in the configuration settings (`time_zone`).


## v1.4.2 – Updates on Omnia Export Behavior, Dark Mode, Refactoring, and Bug Fixes

This version introduces a series of minor bug fixes, changes, and refactoring efforts. Here are the details:

- Omnia Export: Entries that already have an Omnia ID set in Baserow can no longer be exported to Omnia. This prevents unintentional multiple exports of uploads. To re-export an upload to Omnia, simply delete the Omnia ID of the upload in Baserow.
- Added headers to the Server Sent Events for Export Notifications: The SSE response now includes headers to prevent them from being cached in nginx.
- Date and times in filenames are now correctly set in the timezone defined in the config.
- Replaced Typer with argparse: The CLI framework Typer has been replaced with the built-in argparse module, as the complexity of Typer was not justified for this application.
- Removed the legacy module noco_upload from the codebase.
- Cleaned up import statements in all files and replaced all relative paths with absolute import paths.
- Confirmation emails reflect the medium of the show (Radio, Podcasts, TV). This improves differentiation between different types and simplifies working with uploads. The medium type is explicitly listed as a property in internal emails.
- Internal confirmation email after upload: Internal confirmation emails now include comments from the uploader to ALEX.
- Our frontend framework Bulma has been updated to version 1. This enables the frontend to display in Dark Mode when the user's system is set to Dark Mode.
- Refactoring and Documentation of Configuration: Both the Python module and config files have been cleaned up and now include comments.


## v1.4.3 – Fix time zone bug in mail notifications

Time zones of the broadcast time are now correctly taken into account in mails 


## v1.4.3a – Fix invalid newlines by autopep8

autopep broke the `baserow_orm.py` file by adding invalid newline within the format string.


## v1.4.4 – Global Notification

Adds the option to globally display a notification to the user. The notification is themed to match the levels (info, success, warn, error). The notification is displayed on all pages. The rendering is done on the server side and is therefore also displayed without Javascript.


## v1.4.5 – ???

- The text in the logo is now exported as a path. The logo is now displayed correctly regardless of locally installed fonts.


## v1.5.0 – News segments and ntfy notifications

- Supports new media type »News« for news segments.
- Infrastructure added for sending notifications via Ntfy.sh. Currently only used for internal notification on newly uploaded news segments.


## v1.5.1 – Minor tweaks

- feat: ntfy messages now support tags
- feat: newspaper emoji on ntfy notifications for newly uploadednews segments
- fix: `secrets.tpl.toml` updated (now includes the ntfy topic)


## v1.5.2 – States for news segments

- States for news segments export to mAirList are now correctly set.
- improvement: ntfy module is now more ergonomic to use.
- improvement: Technical preparation for switching internal notification to ntfy.sh