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
  minuten. Daarna kan de algemene achturige streeftijdaanvulling worden
  toegepast.
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
  beneden en het einde naar boven. Daarna probeert de planner de streefduur
  binnen de ingestelde tijd- en CAO-grenzen te behalen.
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

## Volledige beslisboom

Hieronder staat de uitvoeringsvolgorde van `./generate`. Een hogere stap wordt
altijd eerder uitgevoerd dan een lagere stap. Een uitsluiting in stap 4 stopt
de beoordeling van die activiteit; latere bezettingsregels kunnen een
uitgesloten activiteit dus niet opnieuw activeren.

### 1. Bron kiezen en PDF uitlezen

1. Los de productiereferentie op en kies de nieuwste PDF uit `input/`.
2. Lees titel, planningsperiode, accountnummer, pagina's, datums, tijden,
   locaties, activiteiten, pauzes, details en losse annotaties.
3. Normaliseer Nederlandse en Engelse vaste termen naar dezelfde interne
   activiteitstypen.
4. Laat een eindtijd die vóór de begintijd ligt doorlopen op de volgende
   kalenderdag.
5. Bewaar bronpagina en bronregel bij ieder item zodat iedere beslissing
   herleidbaar blijft.

### 2. Conditionele vragen en vereisten

1. Bepaal welke vragen op de productie van toepassing zijn.
2. Neem een expliciet antwoord uit `answers/decisions.json`; als dat ontbreekt,
   probeer alleen de geconfigureerde veilige gevolgtrekkingen uit de PDF.
3. Voor DNO wordt gevraagd of decorinbouw nodig is.
4. Bij `nee` ontstaat geen Montagehalvereiste.
5. Bij `ja`:
   - gebruik een bestaand passend Montagehal-/decorinbouwmoment;
   - maak anders een moment aan uit `day`, `start` en `end` in het antwoord;
   - ontbreken die gegevens ook, markeer het vereiste als niet ingepland.
6. Een open blokkerende vraag of een niet ingepland verplicht vereiste leidt
   later tot status `invoer_nodig`.

### 3. Dagafsluiting bepalen

Per dag wordt de eerste passende afsluitregel gebruikt:

| Marker | Betekenis | Benodigde tijd na laatste AVM-event |
|---|---|---:|
| `Afsluiten` / `Afsluiting` | overstaan | 30 minuten |
| `Afbouw` | niet overstaan | 60 minuten |

Deze tijd wordt als daguitloop op de AVM-events van die dag gezet. Een
specifieke dienstregel kan expliciet zijn eigen eindtijd behouden, zoals de
zondagregel `10:00-18:00`, maar alleen wanneer die eindtijd de benodigde
uitloop volledig bevat.

### 4. Iedere activiteit afzonderlijk beoordelen

Voor ieder item wordt deze beslisboom doorlopen:

1. **Valt het vóór de reguliere AVM-periode?**
   - De periode begint op de dag van de eerste Hoofdtoneel-activiteit.
   - Proefbouw, OT, cast-en-huispresentatie, grote DNO-studiorepetitie,
     voorbereiden/belichten, oplevering decor en Montagehalwerk zijn
     geconfigureerde vroege uitzonderingen.
   - Geen uitzondering: stop met reden `Buiten AVM-roosterperiode`.
2. **Past een uitsluiting?** De eerste passende uitsluiting wint:
   - Operastudio's en Het Concertgebouw;
   - technische tijd;
   - licht richten;
   - reguliere HNB-balletrepetities, behalve de benoemde uitzonderingen;
   - repetities in een studio/Grote Studio, behalve de grote
     DNO-studiorepetitie.
   - Bij een match: stop met reden `Geen AVM volgens uitsluiting`.
3. **Pas alle passende bezettingsregels toe.**
   - Het hoogste vereiste aantal blijft staan.
   - Planniveau, maximumbezetting, voorkeurspositie, standaardpositie en
     flexibele posities worden uit de passende regels overgenomen.
   - Een conditionele regel geldt alleen als het bijbehorende antwoord matcht.
4. **Pas locatiebezettingsregels toe.**
   - Deze stap bestaat in de planner, maar
     `location_staffing_rules` is momenteel leeg.
5. **Bereken de oproeptijd.**
   - Een regel met gewerkte minuten loopt terug vanaf aanvang en telt
     geconfigureerde lunch-/dinerpauzes niet als werktijd.
   - Een regel met gewone minuten trekt die rechtstreeks van de aanvang af.
   - Een berekende oproeptijd van exact 12:00 wordt naar 11:30 gecorrigeerd.
6. **Bepaal de status.**
   - Bezetting gevonden: status volgt het planniveau.
   - Anders een expliciete vereiste tekstmatch: één verplichte AVM.
   - Anders een mogelijke AVM-term: `controleren`.
   - Een geconfigureerde negeerterm voorkomt die controlemarkering.
   - Een losse, niet eenduidig gekoppelde `AVM`-annotatie wordt
     `controleren`.

De actieve bezettings- en aanwezigheidsregels zijn:

| Activiteit/geval | Bezetting | Oproep/venster | Niveau/bijzonderheid |
|---|---:|---|---|
| Proefbouw | AVM1 | activiteit zelf, geen buffer | verplicht |
| OT/ontwerpteam | AVM1 | standaardbuffer | verplicht, verhindering controleren |
| DNO cast-en-huispresentatie | AVM1 | standaardbuffer | verplicht |
| DNO voorbereiden belichten, eerste Hoofdtoneeldag | AVM1 | standaardbuffer | gebruikelijk |
| Zelfde, decorinbouw bevestigd | AVM1 + AVM2 | standaardbuffer | verplicht |
| Grote DNO-studiorepetitie | AVM1 | standaardbuffer | verplicht |
| DNO Montagehal/decorinbouw | AVM1 | standaardbuffer | verplicht |
| Oplevering decor | één flexibele AVM | standaardbuffer | richtlijn |
| RR op Hoofdtoneel | AVM1 + AVM2 | 2 uur vooraf | verplicht |
| Piano CD | AVM1 + AVM2 | standaardbuffer | verplicht, lage TEAM-prioriteit |
| Voorstelling/schoolvoorstelling | AVM1 + AVM2 | 2 gewerkte uren vooraf; 1 uur na showeinde | verplicht |
| Generale | AVM1 + AVM2 | speciaal relatief venster | verplicht |
| VGO/PVG | AVM1 + AVM2 | 2 gewerkte uren vooraf; 30/60 min uitloop | verplicht |
| OTR | AVM1 + AVM2 | 2 gewerkte uren vooraf | verplicht |
| Zit/Sitzprobe (`ZIT`) | AVM1 + AVM2 | gelijk aan OTR | verplicht |
| Pianotoneelrepetitie | AVM1 + AVM2 | standaard vooraf; 30 min erna | verplicht |
| Technische repetitie | één AVM, voorkeur AVM1 | standaardbuffer | verplicht |
| CD-toneelrepetitie | één flexibele AVM | standaardbuffer | verplicht |
| Belichten | exact één flexibele AVM | 30 min voor en na | verplicht |
| Orkestrepetitie op Hoofdtoneel | AVM1 + AVM2 | standaardbuffer | verplicht |
| Solistenrepetitie | AVM1 + AVM2 | 30 min voor en na | verplicht |

`Standaardbuffer` betekent momenteel één uur vóór en één uur na de
activiteit, tenzij een afsluitmarker of specifiekere regel de eindtijd
vervangt.

### 5. Eerste verdeling over AVM1 en AVM2

1. Zet `richtlijn` en `gebruikelijk` tijdelijk apart.
2. Zet ieder hard event met bezetting twee direct bij AVM1 én AVM2.
3. Zet optionele events tijdelijk apart.
4. Verdeel flexibele verplichte events op datum/tijd:
   - voorkom eerst overschrijding van de maximale dienstduur;
   - kies daarna de variant die het dichtst bij acht uur komt;
   - gebruik daarna een expliciete persoonsvoorkeur;
   - gebruik daarna de variant met de minste events;
   - bij een volledige gelijke stand is AVM1 de vaste technische tie-break.
5. Een flexibel event langer dan acht uur wordt in twee aansluitende delen
   gesplitst en over AVM1/AVM2 verdeeld volgens dezelfde score.
6. Voeg zachte events toe in volgorde `richtlijn`, daarna `gebruikelijk`, maar
   alleen als de volledige benodigde bezetting zonder CAO-conflict past.
7. Voeg optionele events als laatste toe, alleen wanneer:
   - die persoon die dag al een dienst heeft;
   - het event niet met een bestaand event overlapt;
   - de bestaande dienst er niet langer door wordt.

### 6. Diensten per persoon en dag berekenen

1. Verzamel alle toegewezen events per kalenderdag.
2. Bepaal per event het verplichte aanwezigheidsvenster:
   - gebruik eerst de eerste passende speciale dienstregel;
   - gebruik anders de expliciete oproeptijd of de activiteitbuffer;
   - gebruik de daguitloop uit stap 3 waar die leidend is.
3. Speciale dienstregels worden in deze volgorde geprobeerd:
   - één zondagvoorstelling om 14:00: `10:00-18:00`, alleen bij één
     voorstelling en voldoende uitloop/afbouwruimte;
   - schoolvoorstelling om 13:30;
   - voorstelling om 14:00;
   - overige voorstelling;
   - generale om 14:00: `10:00-18:00`;
   - overige generale: 4,5 uur vóór tot 4 uur na aanvang.
4. Neem de vroegste vereiste start en de laatste vereiste eindtijd van de dag.
5. Bereken de basisdienst:
   - past alles binnen 09:00-17:00, gebruik dan 09:00-17:00;
   - is het verplichte venster langer dan acht uur, behoud dat hele venster;
   - anders verschuif een achtuursblok zodat het verplichte venster past;
   - regels met `preserve_required_window` behouden eerst hun exacte venster.
6. Bij twee voorstellingen blijven AVM1 en AVM2 op beide shows. Is het
   natuurlijke venster langer dan 13,5 uur, behoud dan de laatste 13,5 uur.
7. Rond de start naar beneden en het einde naar boven af op halve uren.
8. Pas de 12:00-naar-11:30-startcorrectie toe, tenzij daardoor de maximale
   dienstduur wordt overschreden.
9. Vul een dienst korter dan acht uur aan:
   - probeer eerst de start te vervroegen;
   - streeftijdaanvulling gaat nooit vóór 09:00;
   - een verplichte oproeptijd vóór 09:00 blijft wel staan;
   - begrens de vervroeging door 11 uur rust na de vorige dienst;
   - zet het resterende tekort aan het einde;
   - begrens die verlenging door 11 uur rust vóór de volgende dienst;
   - kan geen van beide volledig, laat de dienst korter en meld dit.
10. Controleer de harde grenzen:
    - maximaal 13,5 uur dienstduur;
    - minimaal 11 uur rust tussen opeenvolgende diensten.

### 7. CAO-conflicten met TEAM-AVM proberen op te lossen

Zolang een primaire dienst een CAO-conflict heeft, herhaalt de planner
maximaal 500 keer:

1. Bekijk eerst AVM1, daarna AVM2, en daarbinnen de diensten op datum.
2. Maak een lijst van events die uit de conflictdienst mogen worden verplaatst.
3. Proefbereken voor iedere kandidaat de primaire dienst zonder dat event.
4. Sorteer kandidaten achtereenvolgens op:
   - vervangingsprioriteit;
   - aantal resterende CAO-conflicten;
   - totale resterende overschrijding;
   - expliciet TEAM-vervangbaar vóór alleen-noodzakelijk-vervangbaar;
   - kortere activiteit;
   - starttijd en stabiel event-ID.
5. Verplaats de beste kandidaat naar een bestaande passende TEAM-AVM of maak
   een nieuwe TEAM-AVM aan.
6. Herbereken alle diensten en stop wanneer geen conflict of geen toegestane
   verplaatsing meer bestaat.

Proefbouw, OT en de DNO cast-en-huispresentatie zijn vaste primaire events en
worden niet verplaatst. Bij een voorstelling moet altijd minimaal één van
AVM1/AVM2 aanwezig blijven.

De numerieke TEAM-volgorde is laag naar hoog:

| Prioriteit | Activiteiten |
|---:|---|
| 0 | Piano CD, belichten, CD-toneelrepetitie |
| 2 | Pianotoneelrepetitie |
| 3 | Technische repetitie |
| 4 | Solistenrepetitie |
| 5 | Orkestrepetitie |
| 8 | VGO/PVG |
| 9 | Generale |
| 10 | OTR en ZIT |
| 20 | Voorstelling/schoolvoorstelling; minimaal één primaire AVM blijft |
| 100 | Geen specifieke prioriteitsregel; alleen indien toegestaan en nodig |

### 8. Dekking, status en uitvoer

1. Tel per bron-event hoeveel unieke posities het dekken, inclusief TEAM-AVM.
2. Voeg een blokkerende reden toe voor:
   - een open blokkerende vraag;
   - een niet ingepland conditioneel vereiste;
   - onvoldoende dekking van een verplicht event.
3. Verzamel ieder overgebleven dienstduur- of rustconflict.
4. Bepaal de uitvoerstatus:
   - blokkerende reden: `invoer_nodig`;
   - anders een CAO-conflict, waarschuwing, annotatie, open niet-blokkerende
     vraag of `controleren`-event: `concept_met_conflicten`;
   - anders: `concept`.
5. Schrijf CSV, tekstrooster, alle events, issues en het volledige
   controlebestand. Dit blijft altijd conceptuitvoer voor menselijke controle.

## Roosterberekening

Het controlebestand bevat de volledige extractie. De CSV is bedoeld om snel te
filteren of gegevens voorlopig handmatig naar Excel over te nemen. Het
tekstbestand bevat een compact dagoverzicht van de verplichte AVM-events.
Activiteiten zonder bekende aanwezigheidstijd worden niet gegokt, maar als
`NTB` weergegeven. In het rooster worden OTR, ZIT, VGO en PVG als vaste
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
