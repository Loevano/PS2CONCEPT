# Offline Auto Planner

Auto Planner zet een NO&B-productieplanning uit PDF om naar een
controleerbaar conceptrooster. Alle verwerking gebeurt lokaal. De bron-PDF
wordt niet gewijzigd en de applicatie schrijft niet naar het definitieve
Excel-bestand.

## Dagelijks gebruik

Maak vanuit de hoofdmap van Auto Planner eerst de productie aan:

```bash
./add 2627 cinderella
```

Dit maakt alle benodigde mappen:

```text
producties/
└── 2627/
    └── cinderella/
        ├── production.json
        ├── input/
        ├── answers/
        ├── output/
        └── archive/
```

Plaats vervolgens een of meer aangeleverde plannings-PDF's in:

```text
producties/2627/cinderella/input/
```

Genereer daarna alle uitvoer:

```bash
./generate cinderella
```

`generate` mag steeds opnieuw worden uitgevoerd en vervangt alle gegenereerde
uitvoer. Als er meerdere PDF's in `input/` staan, gebruikt Auto Planner
automatisch de PDF die het laatst is aangemaakt of gewijzigd. Oude PDF's mogen
dus blijven staan.

Als dezelfde productienaam in meerdere seizoenen bestaat, is alleen de naam
niet eenduidig. Gebruik dan bijvoorbeeld:

```bash
./generate 2627-cinderella
```

De uitvoer staat in `producties/2627/cinderella/output/`:

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

## Eenmalige installatie

De virtuele Python-omgeving is alleen een technische installatievoorwaarde.
Een gebruiker maakt deze één keer aan; voor dagelijks gebruik zijn alleen
`./add` en `./generate` nodig.

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Huidige afbakening

- Activiteiten, datums, tijden, locaties en toelichtingen worden uit het
  productieschema gelezen.
- Zowel de Nederlandse als de Engelse NO&B-PDF-structuur wordt herkend.
  Engelstalige metadata, weekdagen, maanden, locaties en vaste
  activiteitstermen worden bij extractie naar dezelfde interne begrippen
  genormaliseerd als de Nederlandstalige planning.
- Eindtijden na middernacht krijgen automatisch de volgende kalenderdatum.
- De reguliere AVM-roosterperiode begint op de dag van de eerste activiteit op
  het Hoofdtoneel. Proefbouw, OT, de opera-presentatie van cast en huis, de
  grote DNO-studiorepetitie, voorwaardelijk Montagehalwerk en expliciete
  DNO-voorbereidingsactiviteiten zijn vroege uitzonderingen.
- Proefbouw en OT worden aan AVM1 toegewezen. Voor een proefbouw wordt geen
  extra opbouw- of afbouwtijd ingepland. OT-beschikbaarheid blijft als
  handmatig controlepunt bij het event staan.
- Alleen bij DNO-opera wordt de presentatie van cast en huis aan AVM1
  toegewezen. Een conflict wordt geflagd en niet stilzwijgend vervangen.
- Studiorepetities worden niet geroosterd. Reguliere repetities van een
  HNB-balletproductie worden niet geroosterd. Op het Hoofdtoneel zijn CD-, SR-,
  OR-, orkesttoneel-, pianotoneel- en generale repetities expliciete
  uitzonderingen. In de Grote Studio is bij deze repetities geen AVM nodig;
  de grote studiorepetitie van DNO blijft een afzonderlijke uitzondering.
- Activiteiten in de Operastudio's en in Het Concertgebouw worden niet voor
  AVM geroosterd, ongeacht het activiteitstype.
- Bij DNO is opbouwen/voorbereiden voor belichten alleen op de eerste
  bijbehorende dag op het Hoofdtoneel een voorbereidingsmoment voor AVM1 met
  planniveau `gebruikelijk`. Alleen wanneer decorinbouw is bevestigd, worden
  AVM1 en AVM2 geroosterd.
- Bij een DNO-productie vraagt de planner of er iets in het decor moet worden
  ingebouwd. Bij `ja` moet een Montagehalmoment bestaan of via een
  antwoordenbestand van datum en tijd worden voorzien. Zonder antwoord blijft
  het rooster `invoer_nodig`.
- Licht richten en technische tijd worden niet geroosterd. Oplevering van het
  decor is een richtlijn: inplannen zolang dit zonder CAO-conflict kan.
- Belichten vereist precies één AVM'er, aanwezig vanaf minimaal 30 minuten voor
  aanvang. Een regierepetitie op het Hoofdtoneel vereist AVM1 en AVM2, beiden
  vanaf minimaal twee uur vooraf.
- Piano CD vereist AVM1 en AVM2, maar is bij conflictoplossing een vroege
  kandidaat voor TEAM-AVM-overname.
- De huidige bedrijfsregels vereisen twee AVM'ers bij iedere voorstelling
  (inclusief schoolvoorstelling), alle generales en orkest-gerelateerde
  repetities zoals orkestrepetitie, orkesttoneelrepetitie en voorgenerale orkest.
- Bij OTR, ZIT (Zit/Sitzprobe), VGO en PVG zijn de AVM'ers minimaal twee gewerkte uren voor aanvang
  aanwezig; lunch- en dinerpauzes tellen niet mee.
- HNB-pianotoneelrepetities staan bij voorkeur met twee AVM'ers, maar kunnen
  bij CAO-druk per situatie naar TEAM-AVM worden verplaatst.
- Bij een VGO of PVG begint de AVM-dienst minimaal twee gewerkte uren voor
  aanvang, exclusief pauzes. Bij
  overstaan wordt 30 minuten afbouwtijd ingepland; bij niet overstaan 60
  minuten. Deze dienst wordt niet kunstmatig tot acht uur verlengd.
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
  de werkdag maximaal 13,5 uur duurt (inclusief 30 minuten lunchpauze en 60
  minuten dinerpauze) en minimaal elf uur rust behouden blijft.
- Verplichte activiteiten blijven gedekt. Een voorkeur voor AVM1/AVM2 mag bij
  CAO-druk door TEAM-AVM worden overgenomen; activiteitprioriteit en
  persoonsvoorkeur zijn afzonderlijke beslissingen.
- Zit/Sitzprobe heeft code `ZIT` en dezelfde dubbele bezetting en
  vervangingsprioriteit als OTR.
- Orkestrepetities op het Hoofdtoneel en solistenrepetities vereisen twee
  AVM'ers: AVM 1 en AVM 2.
- Bij voorstellingen en schoolvoorstellingen geldt een minimale
  aanwezigheidstijd van twee gewerkte uren vóór aanvang. Lunchpauze (30
  minuten) en dinerpauze (60 minuten) tellen daarbij niet mee. De planner kan
  eerder beginnen om de streefduur van acht uur te halen.
- Een schoolvoorstelling om 13:30 met een lunchpauze in de aanlooptijd begint
  daarom om 11:00.
- Op dagen met twee voorstellingen draaien AVM1 en AVM2 beide voorstellingen.
  Als de normale aanwezigheid langer dan 13,5 uur zou duren, wordt de
  voorbereiding vóór de eerste voorstelling ingekort en worden de laatste
  13,5 uur van de dag geroosterd.
- Een berekende AVM-dienststart van exact 12:00 wordt normaal naar 11:30
  vervroegd. Deze correctie vervalt wanneer de werkdag daardoor langer dan
  13,5 uur wordt. De activiteitstijd uit de bron-PDF
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
Open vragen worden na de eerste generatie geschreven naar
`answers/decisions.json`. Vul daar bijvoorbeeld in:

```json
{
  "decor_inbouw_nodig": {
    "value": "ja"
  }
}
```

Bij `decor_inbouw_nodig: ja` kan het antwoord ook `day`, `start` en `end`
bevatten. Als er nog geen passend Montagehalmoment in de bronplanning staat,
maakt de planner daarmee een expliciet, herleidbaar moment aan.

## Roosterberekening

Het controlebestand bevat de volledige extractie. De CSV is bedoeld om snel te
filteren of gegevens voorlopig handmatig naar Excel over te nemen. Het
tekstbestand bevat een compact dagoverzicht van de verplichte AVM-events.
Activiteiten zonder bekende aanwezigheidstijd worden niet gegokt, maar als
`NTB` weergegeven. In het rooster worden OTR, VGO en PVG als vaste
werkzaamheidscodes gebruikt.

Een standaarddag is 09:00-17:00. Gewone activiteiten moeten vanaf één uur voor
aanvang tot één uur na afloop worden afgedekt; als nodig verschuift het
achtuursblok. Bij OTR, VGO en PVG begint de vereiste aanwezigheid minimaal
twee gewerkte uren voor aanvang; pauzes tellen niet mee. Bij belichten hoeft AVM pas 30 minuten voor aanvang
aanwezig te zijn en 30 minuten na afloop te blijven. Bij een solistenrepetitie
is AVM eveneens 30 minuten voor aanvang aanwezig en blijft AVM 30 minuten na
afloop. Na een pianotoneelrepetitie hoeft AVM nog 30 minuten te blijven.
Voorstellingen en schoolvoorstellingen beginnen minimaal twee gewerkte uren voor
aanvang; een aanwezige lunchpauze van 30 minuten en dinerpauze van 60 minuten
worden vóór die aanlooptijd toegevoegd. De dienst eindigt één uur na de
werkelijke eindtijd van de voorstelling.
Bij één voorstelling op zondag om 14:00 is de dienst vast 10:00-18:00, mits
18:00 ook de vereiste uitloop of afbouw na de show volledig dekt. Anders wordt
de eindtijd vanaf de werkelijke showeindtijd berekend. Deze regel geldt niet op
een zondag met twee voorstellingen.
Generale repetities behouden het relatieve venster van 4,5 uur vóór tot 4 uur
na aanvang. Een generale met aanvang 14:00 wordt 10:00-18:00 geroosterd.
Het tekstrooster vermeldt afwijkingen van de streefduur niet in de opmerkingen.
Diensten die korter uitkomen, beginnen eerst eerder om de achturige streefduur
te halen, maar de extra streeftijdaanvulling vervroegt een dienst nooit tot vóór
09:00. Als de aanvulling aan de voorkant daardoor of door de minimale nachtrust
niet volledig kan, wordt de resterende tijd aan het einde toegevoegd. Een
verplichte oproeptijd vóór 09:00 blijft wel leidend. Beide aanvullingen stoppen
zodra anders minder dan elf uur nachtrust tot een aangrenzende dienst
overblijft. De toegevoegde tijd staat als opmerking vermeld.
Diensten boven 13,5 uur en minder dan elf uur rust worden automatisch
opgelost door activiteiten naar TEAM-AVM-diensten te verplaatsen; als dat niet
lukt, blijft een CAO-conflict zichtbaar en krijgt het gehele rooster de status
`ongeldig_cao`.

Ontwikkelaars kunnen alle tests uitvoeren met:

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
