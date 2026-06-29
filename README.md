# Offline Auto Planner

Deze eerste versie zet een NO&B-productieplanning uit PDF om naar controleerbare
JSON- en CSV-bestanden. Alle verwerking gebeurt lokaal. De bron-PDF wordt niet
gewijzigd en de applicatie schrijft bewust nog niet naar het definitieve
Excel-bestand.

## Productiedossiers

De aanbevolen workflow gebruikt voor iedere productie een zelfstandig dossier.
Maak bijvoorbeeld een dossier voor Cinderella:

```bash
.venv/bin/auto-planner init 2627-cinderella
```

Hiermee ontstaat:

```text
productions/2627-cinderella/
├── production.json
├── input/
├── answers/
├── output/
└── archive/
```

Plaats de geleverde planning als `input/planning.pdf`. Een andere PDF-naam werkt
ook zolang er precies één PDF in `input/` staat. Genereer daarna het
conceptrooster:

```bash
.venv/bin/auto-planner generate productions/2627-cinderella
```

Voor dagelijks gebruik is ook een kort shellcommando beschikbaar. Dit gebruikt
automatisch de virtuele Python-omgeving:

```bash
./generate 2627-cinderella
```

Als het productiedossier nog niet bestaat, maakt dit commando eerst automatisch
de volledige mappenstructuur aan. Plaats daarna de PDF in de gemelde `input/`-map
en voer hetzelfde commando opnieuw uit.

De vaste uitvoer is:

```text
output/
├── concept-rooster.csv
├── concept-rooster.txt
├── events.txt
├── controle.json
└── issues.txt
```

`concept-rooster.csv` bevat één regel per voorgestelde AVM-dienst en is bedoeld
voor overname naar het bestaande Excel-rooster. `events.txt` bevat de volledige
eventbeoordeling. `controle.json` bewaart de herleidbare extractie en
`issues.txt` verzamelt open vragen, conflicten, aannames en waarschuwingen.

De mogelijke dossierstatussen zijn `invoer_nodig`, `concept` en
`concept_met_conflicten`. Alle uitvoer blijft een concept en moet handmatig
worden gecontroleerd. Een CAO-conflict verhindert het genereren niet. Als
noodzakelijke productie-invoer ontbreekt, maakt de planner
`answers/decisions.json` aan. Vul dit bestand in en voer hetzelfde
`generate`-commando opnieuw uit.

## Uitvoer genereren

De onderstaande losse generator blijft beschikbaar voor bestaande workflows.
De Cinderella-PDF is voorlopig als standaardinput gekoppeld in
[`generate_output.py`](generate_output.py). Alle uitvoer opnieuw genereren:

```bash
.venv/bin/python generate_output.py
```

Hiermee worden `output/cinderella.json`, `output/cinderella.csv`,
`output/cinderella.txt`, `output/cinderella_avm_rooster.txt` en
`output/cinderella_avm_events.txt` gemaakt. `output/cinderella.txt` bevat een
compact dagoverzicht met datum, tijdspan, duur, eventafkortingen en de
chronologische volgorde. `output/cinderella_avm_rooster.txt` bevat de
personeelsroosters van AVM 1, AVM 2 en eventuele TEAM-AVM-overname diensten
die nodig zijn om CAO-conflicten op te lossen. Het AVM-eventsbestand bevat alle
verplichte AVM-events, kandidaten en losse bronnotities. Onderaan staat ook
`GEEN AVM NODIG`, zonder pauzes en losse tijdmarkeringen. JSON en CSV bewaren
de volledige bronextractie en controlepunten.

Daarnaast wordt `output/roosterregels.txt` gegenereerd. Dit bestand bundelt de
AVM-bedrijfsregels, actieve planningslogica, afkortingen en CAO-regels. Het
maakt expliciet welke CAO-controles nog een volledig persoonlijk rooster nodig
hebben.
Een andere PDF kan later zonder codewijziging:

```bash
.venv/bin/python generate_output.py --pdf "Documentation/andere planning.pdf" --name andere-planning
```

## Huidige afbakening

- Activiteiten, datums, tijden, locaties en toelichtingen worden uit het
  productieschema gelezen.
- Eindtijden na middernacht krijgen automatisch de volgende kalenderdatum.
- De reguliere AVM-roosterperiode begint op de dag van de eerste activiteit op
  het Hoofdtoneel. Proefbouw, OT, de opera-presentatie van cast en huis, de
  grote DNO-studiorepetitie, voorwaardelijk Montagehalwerk en expliciete
  DNO-voorbereidingsactiviteiten zijn vroege uitzonderingen.
- Proefbouw en OT worden aan AVM1 toegewezen. OT-beschikbaarheid blijft als
  handmatig controlepunt bij het event staan.
- Alleen bij DNO-opera wordt de presentatie van cast en huis aan AVM1
  toegewezen. Een conflict wordt geflagd en niet stilzwijgend vervangen.
- Studiorepetities worden niet geroosterd. Reguliere repetities van een
  HNB-balletproductie worden niet geroosterd. Op het Hoofdtoneel zijn CD-, SR-,
  OR-, orkesttoneel-, pianotoneel- en generale repetities expliciete
  uitzonderingen. In de Grote Studio is bij deze repetities geen AVM nodig;
  de grote studiorepetitie van DNO blijft een afzonderlijke uitzondering.
- Bij DNO is opbouwen/voorbereiden voor belichten een voorbereidingsdag voor
  AVM1 en heeft dit het planniveau `gebruikelijk`. Alleen wanneer decorinbouw
  is bevestigd, worden AVM1 en AVM2 geroosterd.
- Bij een DNO-productie vraagt de planner of er iets in het decor moet worden
  ingebouwd. Bij `ja` moet een Montagehalmoment bestaan of via een
  antwoordenbestand van datum en tijd worden voorzien. Zonder antwoord blijft
  het rooster `invoer_nodig`.
- Licht richten en technische tijd worden niet geroosterd. Oplevering van het
  decor is een richtlijn: inplannen zolang dit zonder CAO-conflict kan.
- Belichten vereist precies één AVM'er, aanwezig vanaf minimaal 30 minuten voor
  aanvang. Een DNO-regierepetitie staat bij AVM1 vanaf minimaal één uur vooraf.
- Piano CD vereist AVM1 en AVM2, maar is bij conflictoplossing een vroege
  kandidaat voor TEAM-AVM-overname.
- De huidige bedrijfsregels vereisen twee AVM'ers bij iedere voorstelling
  (inclusief schoolvoorstelling), alle generales en orkest-gerelateerde
  repetities zoals orkestrepetitie, orkesttoneelrepetitie en voorgenerale orkest.
- HNB-pianotoneelrepetities staan bij voorkeur met twee AVM'ers, maar kunnen
  bij CAO-druk per situatie naar TEAM-AVM worden verplaatst.
- Bij een voorgenerale blijft de vereiste begintijd leidend: 4,5 uur voor
  aanvang. Bij overstaan wordt 30 minuten afbouwtijd ingepland; bij niet
  overstaan 60 minuten.
- Technische repetities vereisen minimaal één AVM'er met voorkeur voor AVM 1.
- HNB-cd-toneelrepetities en belichten vereisen één AVM'er en mogen door een
  TEAM-AVM worden gedaan.
- Er staat maximaal één AVM'er tegelijk op belichten; de planner verdeelt
  belichten flexibel over AVM 1, AVM 2 en TEAM-AVM bij CAO-druk.
- Bij een CAO-conflict worden eerst belichten en HNB-cd-toneelrepetities naar
  een TEAM-AVM verplaatst, samen met Piano CD; daarna volgen
  HNB-pianotoneelrepetities. Als dat niet genoeg is, mogen ook andere verplichte
  AVM-activiteiten naar TEAM-AVM om dienstduur en rusttijd op te lossen.
- Een langere dienst voor AVM1 of AVM2 heeft altijd voorrang op TEAM-AVM zolang
  de dienst maximaal twaalf uur duurt en minimaal elf uur rust behouden blijft.
- Verplichte activiteiten blijven gedekt. Een voorkeur voor AVM1/AVM2 mag bij
  CAO-druk door TEAM-AVM worden overgenomen; activiteitprioriteit en
  persoonsvoorkeur zijn afzonderlijke beslissingen.
- Orkestrepetities en solistenrepetities vereisen twee AVM'ers: AVM 1 en AVM 2.
- Bij voorstellingen, schoolvoorstellingen en generale repetities geldt een
  aanwezigheidstijd van drie gewerkte uren vóór aanvang. Lunchpauze (30
  minuten) en dinerpauze (60 minuten) tellen daarbij niet mee. De planner kan
  eerder beginnen om de streefduur van acht uur te halen.
- Een schoolvoorstelling om 13:30 begint daarom om 10:00: drie gewerkte uren
  plus een lunchpauze van 30 minuten.
- Op dagen met twee voorstellingen draaien AVM1 en AVM2 beide voorstellingen.
  Als de normale aanwezigheid langer dan twaalf uur zou duren, wordt de
  voorbereiding vóór de eerste voorstelling ingekort en worden de laatste
  twaalf uur van de dag geroosterd. Bij een einde om 00:00 wordt dit dus
  12:00-00:00.
- Een berekende AVM-dienststart van exact 12:00 wordt normaal naar 11:30
  vervroegd. Deze correctie vervalt wanneer de dienst daardoor langer dan de
  harde CAO-grens van twaalf uur wordt. De activiteitstijd uit de bron-PDF
  blijft ongewijzigd.
- AVM-diensttijden worden naar buiten afgerond op halve uren: de start naar
  beneden en het einde naar boven. De andere grens wordt niet verschoven om
  alsnog de streefduur van acht uur te behalen.
- Het tekstrooster bevat een kolom `Overstaan`. Deze krijgt een `x` wanneer de
  dag met `Afsluiten` of `Afsluiting` eindigt; bij `Afbouw` blijft zij leeg.
- Mogelijke aanvullende gevallen zoals `video`, `geluid` en `soundcheck`
  krijgen de status `controleren`.
- Activiteiten voor het richten van licht zijn expliciet uitgesloten van AVM.
- Een losse AVM-notitie waarvan de relatie door de PDF-opmaak niet eenduidig is,
  wordt als aparte bronannotatie bewaard.
- CAO-controle binnen dit productierooster controleert dienstduur en rust tussen
  opeenvolgende diensten. Week- en vierwekentotalen vereisen nog een volledig
  persoonlijk rooster met contractomvang.
- Een conflict met een reeds controleerbare CAO-regel geeft de status
  `ongeldig_cao`. Zo'n uitvoer is alleen diagnostisch en nooit definitief.

## Planniveaus en conditionele invoer

De planner gebruikt vier afzonderlijke planniveaus:

1. `verplicht`: de activiteit moet worden gedekt;
2. `richtlijn`: inplannen zolang dit CAO-technisch haalbaar is;
3. `gebruikelijk`: standaard voorstellen, maar eerder laten vervallen dan een
   richtlijn;
4. `optioneel`: alleen binnen bestaande capaciteit toevoegen.

Een conditionele vraag activeert een regel en is dus geen numerieke prioriteit.
Antwoorden kunnen als JSON worden meegegeven:

```bash
.venv/bin/python generate_output.py \
  --answers config/production_answers.example.json
```

Bij `decor_inbouw_nodig: ja` kan het antwoord ook `day`, `start` en `end`
bevatten. Als er nog geen passend Montagehalmoment in de bronplanning staat,
maakt de planner daarmee een expliciet, herleidbaar moment aan.

## Installeren en uitvoeren

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/auto-planner extract \
  "Documentation/PSB 2627 HNB3 Cinderella v02032026.pdf" \
  --rules config/avm_rules.json \
  --json output/cinderella.json \
  --csv output/cinderella.csv \
  --text output/cinderella.txt \
  --answers config/production_answers.example.json
```

De JSON-uitvoer is het volledige controlebestand. De CSV is bedoeld om snel te
filteren of gegevens voorlopig handmatig naar Excel over te nemen. De
tekstuitvoer bevat een compact dagoverzicht van de verplichte AVM-events.
Activiteiten zonder bekende aanwezigheidstijd worden niet gegokt, maar als
`NTB` weergegeven. In het rooster worden OTR, VGO en PVG als vaste
werkzaamheidscodes gebruikt.

Een standaarddag is 09:00-17:00. Gewone activiteiten moeten vanaf één uur voor
aanvang tot één uur na afloop worden afgedekt; als nodig verschuift het
achtuursblok. Bij belichten hoeft AVM pas 30 minuten voor aanvang aanwezig te
zijn en 30 minuten na afloop te blijven. Na een solistenrepetitie of
pianotoneelrepetitie hoeft AVM nog 30 minuten te blijven. Voorstellingen,
schoolvoorstellingen en generale repetities gebruiken
een relatief venster van 4,5 uur vóór tot 4 uur na de aanvang:
19:30 wordt 15:00-23:30 en 20:00 wordt 15:30-00:00.
Een voorstelling of generale met aanvang 14:00 vormt een uitzondering en wordt
10:00-18:00 geroosterd.
Het tekstrooster vermeldt afwijkingen van de streefduur niet in de opmerkingen.
Diensten die korter uitkomen, worden aan het einde tot de achturige streefduur
aangevuld; de toegevoegde tijd staat wel als opmerking vermeld.
Diensten boven twaalf uur en minder dan elf uur rust worden automatisch
opgelost door activiteiten naar TEAM-AVM-diensten te verplaatsen; als dat niet
lukt, blijft een CAO-conflict zichtbaar en krijgt het gehele rooster de status
`ongeldig_cao`.

Tests uitvoeren:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## CAO-model

[`config/cao_rules.json`](config/cao_rules.json) bevat de eerste, expliciet uit
de aangeleverde CAO overgenomen regels voor Techniek/AVM met paginaverwijzing.
Dit is configuratie en bronadministratie. Dienstduur en rust worden al op het
gegenereerde productierooster toegepast; totalen over weken/vier weken worden
pas volledig controleerbaar zodra personeelsdiensten beschikbaar zijn.

Benodigde vervolginvoer:

1. Een geanonimiseerd voorbeeld van de personeelsplanning of het Excel-sjabloon.
2. Per medewerker: afdeling/functie, arbeidspatroon, contractpercentage en
   beschikbaarheid.
3. De bedrijfsregels die bepalen wanneer AVM daadwerkelijk aanwezig moet zijn.
