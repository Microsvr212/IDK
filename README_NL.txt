NOVA | FORTNITE OPTIMIZER 2.0
================================

WAT ZIT ERIN?
- Dashboard met live CPU- en RAM-gebruik.
- Detectie of Fortnite draait.
- Internet-latentietest naar 1.1.1.1 (dit is NIET de ping naar de Fortnite-matchserver).
- Optimizer met aparte Apply- en Undo-knoppen.
- Windows-instellingen snel openen.
- Lokale activity log.
- Vorige waarden worden lokaal bewaard zodat Undo ook na opnieuw openen werkt.

ECHTE, OMKEERBARE TWEAKS
1. High Performance Power Plan
   Activeert het bestaande Windows High Performance energieplan.
   Undo zet het energieplan terug dat actief was voor Apply.
   Het energieplan kan meer energie gebruiken en meer warmte veroorzaken.

2. Windows Game Mode
   Zet AutoGameModeEnabled aan voor de huidige Windows-gebruiker.
   Undo herstelt de originele registerwaarde of verwijdert de waarde als die eerst niet bestond.

3. Background Game Capture uit
   Zet GameDVR_Enabled en AppCaptureEnabled uit voor de huidige gebruiker.
   Dit kan de Windows-opnamefunctie beïnvloeden.
   Undo herstelt beide originele waarden.

4. Fortnite High Performance GPU preference
   Je selecteert of detecteert FortniteClient-Win64-Shipping.exe.
   NOVA zet de Windows GPU-preference voor die executable op High Performance.
   Dit is vooral nuttig op systemen met meerdere GPU's; op een systeem met één GPU levert dit meestal niets extra's op.
   Start Fortnite opnieuw om de nieuwe voorkeur te laten gebruiken. Undo herstelt de eerdere voorkeur of verwijdert de entry als die eerst niet bestond.

5. Windows Transparency uit
   Schakelt transparantie-effecten uit voor de huidige gebruiker.
   Undo herstelt de originele waarde.

6. Windows Visual Performance
   Zet VisualFXSetting op 'best performance' voor de huidige gebruiker.
   Sommige bureaubladeffecten/animaties kunnen verdwijnen.
   Undo herstelt de originele waarde.

EXE BOUWEN ZONDER PYTHON OP JE EIGEN PC
1. Maak een GitHub-repository aan en upload ALLE bestanden en mappen uit deze map.
2. Upload ook de verborgen map .github met daarin workflows/build-windows.yml.
3. Kies op GitHub het tabblad Actions en open Build NOVA for Windows.
4. Klik op Run workflow en daarna nogmaals op Run workflow.
5. Wacht tot de workflow groen is. Open de geslaagde run en download onder Artifacts het bestand NOVA-Windows-EXE.
6. Pak alleen die artifact-ZIP uit. Daarin staat NOVA_Fortnite_Optimizer.exe.

Python wordt alleen automatisch op de GitHub-buildserver gebruikt. Je hoeft Python NIET op je eigen Windows-pc te installeren.

BELANGRIJK
- Deze ontwikkelbundel is bedoeld om op Windows te bouwen. Een Windows-EXE kan niet betrouwbaar op deze Linux-omgeving worden gecompileerd.
- De app verandert niets totdat je zelf op Apply drukt.
- Er is geen garantie op een bepaalde FPS- of pingverbetering.
- De internettest naar 1.1.1.1 is alleen een algemene verbindingstest en niet de Fortnite-serverping.
- NOVA injecteert niet in Fortnite, wijzigt geen gamebestanden en probeert anti-cheat niet te beïnvloeden.
- De status en herstelgegevens staan in %LOCALAPPDATA%\NovaFortniteOptimizer.
- Verwijder die map niet zolang je nog Undo wilt kunnen gebruiken.
- De app vraagt niet automatisch om administratorrechten; de opgenomen tweaks zijn bedoeld voor de huidige Windows-gebruiker of het energieplan.

PRIVACY
- Geen account en geen telemetry.
- CPU/RAM en processtatus worden lokaal uitgelezen.
- Alleen wanneer je zelf op Test connection drukt, voert de app een ping uit naar 1.1.1.1.
