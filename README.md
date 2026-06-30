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

De planner doet op dit moment het volgende:

- Leest activiteiten, datums, tijden, locaties en toelichtingen uit Nederlandse
  en Engelse NO&B-planningen.
- Zet Engelse termen automatisch om naar dezelfde interne begrippen als de
  Nederlandse planning.
- Zet een eindtijd na middernacht op de volgende kalenderdag.

**Wat valt binnen het rooster?**

- De reguliere periode start bij de eerste activiteit op het Hoofdtoneel.
  Proefbouw, OT, cast-en-huispresentatie, de grote DNO-studiorepetitie,
  Montagehalwerk en DNO-voorbereiding kunnen eerder vallen.
- Studiorepetities en reguliere HNB-repetities worden niet geroosterd.
  Uitzonderingen op het Hoofdtoneel zijn CD, SR, OR, OTR, PTR en generale.
- In de Grote Studio is voor deze repetities geen AVM nodig. De grote
  DNO-studiorepetitie is de uitzondering.
- Activiteiten in de Operastudio's en Het Concertgebouw vallen buiten het
  AVM-rooster.
- Licht richten en technische tijd worden niet geroosterd.
- Onduidelijke gevallen zoals `video`, `geluid` en `soundcheck` krijgen
  `controleren`.

**DNO-afspraken**

- Proefbouw en OT gaan naar AVM1. Proefbouw heeft geen extra op- of afbouwtijd;
  bij OT wordt de beschikbaarheid handmatig gecontroleerd.
- Cast-en-huispresentatie gaat alleen bij DNO naar AVM1. Conflicten worden
  zichtbaar gemeld.
- Voorbereiden voor belichten telt alleen op de eerste bijbehorende
  Hoofdtoneeldag. Normaal staat daar AVM1; bij bevestigde decorinbouw ook AVM2.
- De planner vraagt of decorinbouw nodig is. Bij `ja` is een Montagehalmoment
  met datum en tijd nodig. Zonder antwoord blijft de status `invoer_nodig`.
- Oplevering decor is een richtlijn en wordt alleen ingepland als dat zonder
  CAO-conflict past.

**Bezetting en tijden**

- Voorstellingen, schoolvoorstellingen, generales, OR, OTR, VGO en PVG hebben
  twee AVM'ers nodig. ZIT heeft dezelfde bezetting en prioriteit als OTR.
- RR op het Hoofdtoneel heeft AVM1 en AVM2 nodig, vanaf twee uur voor aanvang.
- OR op het Hoofdtoneel en SR hebben AVM1 en AVM2 nodig.
- Technische repetitie heeft minimaal één AVM'er, bij voorkeur AVM1.
- Belichten heeft precies één AVM'er, vanaf 30 minuten voor aanvang. De planner
  kiest flexibel uit AVM1, AVM2 en TEAM-AVM.
- Piano CD heeft AVM1 en AVM2 nodig. PTR staat bij voorkeur met twee AVM'ers.
- CD-toneel en belichten mogen bij CAO-druk naar TEAM-AVM.
- Bij OTR, ZIT, VGO, PVG en (school)voorstellingen geldt minimaal twee gewerkte
  uren voorbereiding. Lunch (30 min) en diner (60 min) tellen daarin niet mee.
- VGO/PVG krijgt na afloop 30 minuten bij overstaan en anders 60 minuten.
- Een schoolvoorstelling om 13:30 met lunch in de voorbereiding begint daarom
  om 11:00.
- Bij twee voorstellingen draaien AVM1 en AVM2 beide shows. Boven 13,5 uur
  wordt de voorbereiding ingekort tot de laatste 13,5 uur van de dag.

**Conflicten en afronding**

- Bij CAO-druk gaan Piano CD, belichten en CD-toneel als eerste naar TEAM-AVM,
  daarna PTR. Andere verplichte events volgen alleen als dat nodig is.
- Een langere dienst bij AVM1/AVM2 gaat vóór TEAM-AVM zolang de dienst inclusief
  pauzes maximaal 13,5 uur duurt en er minimaal elf uur rust overblijft.
- Verplichte activiteiten blijven altijd gedekt. Een personeelsvoorkeur mag
  wel worden vervangen.
- Een berekende start om 12:00 wordt normaal 11:30, tenzij de dienst daardoor
  langer dan 13,5 uur wordt. De activiteitstijd uit de PDF verandert niet.
- Diensttijden worden naar buiten afgerond op halve uren. Daarna probeert de
  planner de streefduur van acht uur te halen binnen de CAO-grenzen.
- `Overstaan` krijgt een `x` bij `Afsluiten` of `Afsluiting`, maar niet bij
  `Afbouw`.
- Losse, onduidelijk gekoppelde AVM-notities blijven als bronannotatie bewaard.
- De CAO-controle kijkt naar dienstduur en rust tussen diensten. Week- en
  vierwekentotalen vereisen nog een volledig persoonlijk rooster.
- Een controleerbaar CAO-conflict krijgt `ongeldig_cao`. Die uitvoer is alleen
  bedoeld voor diagnose, niet als definitief rooster.

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

Zo werkt `./generate` van begin tot eind. De planner loopt de genummerde
stappen op volgorde af. Wordt een activiteit in stap 4 uitgesloten, dan is de
beoordeling daarvan klaar. Een latere bezettingsregel kan die activiteit niet
alsnog activeren.

### 1. Bron kiezen en PDF uitlezen

1. Kies de nieuwste PDF uit de folder `input/`.
2. Lees titel, planningsperiode, accountnummer, pagina's, datums, tijden,
   locaties, activiteiten, pauzes, details en losse annotaties.
3. Normaliseer Nederlandse en Engelse vaste termen naar dezelfde interne
   activiteitstypen.
4. Laat een eindtijd die vóór de begintijd ligt doorlopen op de volgende
   kalenderdag.
5. Bewaar bronpagina en bronregel bij ieder item zodat iedere beslissing
   herleidbaar blijft.

### 2. Vragen die van de productie afhangen

1. Kijk welke vragen voor deze productie gelden.
2. Gebruik eerst het antwoord uit `answers/decisions.json`. Staat daar niets,
   dan gebruikt de planner alleen gevolgtrekkingen uit de PDF die vooraf als
   veilig zijn ingesteld.
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

De planner telt deze tijd op bij het laatste AVM-event van die dag. Een
specifieke dienst mag zijn eigen eindtijd houden, bijvoorbeeld zondag
`10:00-18:00`, zolang de benodigde uitloop daar volledig in past.

### 4. Per activiteit bepalen of AVM nodig is

Voor iedere activiteit stelt de planner deze vragen:

1. **Valt de activiteit vóór de eerste Hoofdtoneeldag?**
   - Dan is geen AVM nodig, tenzij het gaat om:
     - proefbouw;
     - OT;
     - cast-en-huispresentatie;
     - de grote DNO-studiorepetitie;
     - voorbereiden voor belichten;
     - oplevering decor;
     - Montagehalwerk.
   - Valt de activiteit onder een uitzondering, dan gaat de beoordeling
     verder. Anders stopt deze met de reden `Buiten AVM-roosterperiode`.
2. **Wanneer is geen AVM nodig?**
   - Als de activiteit in een Operastudio of Het Concertgebouw plaatsvindt.
   - Als het om technische tijd gaat.
   - Als het om licht richten gaat.
   - Als het een reguliere HNB-balletrepetitie is en niet onder een benoemde
     uitzondering valt.
   - Als het een repetitie in een studio of de Grote Studio is, behalve de
     grote DNO-studiorepetitie.
   - Zodra één van deze situaties geldt, stopt de beoordeling met de reden
     `Geen AVM volgens uitsluiting`. Anders gaat de planner verder met de
     bezettingsregels.
3. **Pas alle passende bezettingsregels toe.**
   - Vragen meerdere regels om bezetting, dan blijft het hoogste aantal staan.
   - Planniveau, maximumbezetting, voorkeurspositie, standaardpositie en
     flexibele posities worden uit de passende regels overgenomen.
   - Een conditionele regel geldt alleen als het bijbehorende antwoord matcht.
4. **Pas locatiebezettingsregels toe.**
   - Deze stap bestaat in de planner, maar
     `location_staffing_rules` is momenteel leeg.
5. **Bereken de oproeptijd.**

   ```text
   gewone minuten:
   oproeptijd = aanvang - minuten vooraf

   gewerkte minuten:
   oproeptijd = aanvang - gewerkte minuten - pauzes in dit tijdvak
   ```

   Voorbeelden:
   - Belichten begint om 14:00 en vraagt 30 gewone minuten voorbereiding:
     `14:00 - 00:30 = 13:30`.
   - Een voorstelling begint om 13:30 en vraagt 120 gewerkte minuten. Valt
     daar een lunchpauze van 30 minuten tussen, dan wordt het
     `13:30 - 02:00 - 00:30 = 11:00`.
   - Komt de uitkomst precies op 12:00, dan maakt de planner daar 11:30 van.
     Een RR om 14:00 wordt dus `14:00 - 02:00 = 12:00 → 11:30`.
6. **Bepaal de status.**
   - Bezetting gevonden: status volgt het planniveau.
   - Anders een expliciete vereiste tekstmatch: één verplichte AVM.
   - Anders een mogelijke AVM-term: `controleren`.
   - Een geconfigureerde negeerterm voorkomt die controlemarkering.
   - Een losse, niet eenduidig gekoppelde `AVM`-annotatie wordt
     `controleren`.

De actieve bezettings- en aanwezigheidsregels zijn hieronder gesorteerd op de
prioriteit van de roosterafkortingen. Activiteiten zonder roosterafkorting
staan onderaan.

| Activiteit/geval | Bezetting | Minuten vóór aanvang | Minuten na afloop | Niveau/bijzonderheid |
|---|---:|---:|---:|---|
| Voorstelling/schoolvoorstelling | AVM1 + AVM2 | 120 gewerkte minuten¹ | 60 | verplicht |
| Generale | AVM1 + AVM2 | 270 | 60 | verplicht |
| VGO/PVG | AVM1 + AVM2 | 120 gewerkte minuten¹ | 30 bij overstaan, anders 60 | verplicht |
| OTR | AVM1 + AVM2 | 120 gewerkte minuten¹ | 60 | verplicht |
| Zit/Sitzprobe (`ZIT`) | AVM1 + AVM2 | 120 gewerkte minuten¹ | 60 | verplicht |
| Orkestrepetitie op Hoofdtoneel | AVM1 + AVM2 | 60 | 60 | verplicht |
| RR op Hoofdtoneel | AVM1 + AVM2 | 120 | 60 | verplicht |
| Technische repetitie | één AVM, voorkeur AVM1 | 60 | 60 | verplicht |
| Pianotoneelrepetitie | AVM1 + AVM2 | 60 | 30 | verplicht |
| Solistenrepetitie | AVM1 + AVM2 | 30 | 30 | verplicht |
| CD-toneelrepetitie | één flexibele AVM | 60 | 30 | verplicht |
| Belichten | exact één flexibele AVM | 30 | 30 | verplicht |
| DNO voorbereiden belichten, eerste Hoofdtoneeldag | AVM1 | 30 | 30 | gebruikelijk, gelijk aan belichten |
| Zelfde, decorinbouw bevestigd | AVM1 + AVM2 | 30 | 30 | verplicht, gelijk aan belichten |
| Proefbouw | AVM1 | 0 | 0 | verplicht |
| DNO cast-en-huispresentatie | AVM1 | 0 | 0 | verplicht |
| OT/ontwerpteam | AVM1 | 0 | 0 | verplicht, vergadering; verhindering controleren |
| Grote DNO-studiorepetitie | AVM1 | 60 | 60 | verplicht |
| DNO Montagehal/decorinbouw | AVM1 | 0 | 0 | verplicht |
| Oplevering decor | één flexibele AVM | 0 | 0 | richtlijn |
| Piano CD | AVM1 + AVM2 | 60 | 30 | verplicht, lage TEAM-prioriteit |

¹ Lunch- en dinerpauzes tellen niet mee in de minuten vóór aanvang.

De minuten na afloop worden voor ieder event vanaf de werkelijke eindtijd
berekend, niet vanaf de aanvangstijd.

### 5. Events verdelen over AVM1 en AVM2

1. Zet `richtlijn` en `gebruikelijk` tijdelijk apart.
2. Zet ieder hard event met bezetting twee direct bij AVM1 én AVM2.
3. Zet optionele events tijdelijk apart.
4. Verdeel flexibele verplichte events op datum/tijd:
   - voorkom eerst overschrijding van de maximale dienstduur;
   - kies daarna de variant die het dichtst bij acht uur komt;
   - gebruik daarna een expliciete persoonsvoorkeur;
   - gebruik daarna de variant met de minste events;
   - is alles gelijk, dan kiest de planner AVM1.
5. Een flexibel event langer dan acht uur wordt in twee aansluitende delen
   gesplitst en over AVM1/AVM2 verdeeld volgens dezelfde score.
6. Voeg zachte events toe in volgorde `richtlijn`, daarna `gebruikelijk`, maar
   alleen als de volledige benodigde bezetting zonder CAO-conflict past.
7. Voeg optionele events als laatste toe, alleen wanneer:
   - die persoon die dag al een dienst heeft;
   - het event niet met een bestaand event overlapt;
   - de bestaande dienst er niet langer door wordt.

### 6. Van events naar een dagdienst

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
   - generale om 14:00: start om `10:00`, einde één uur na afloop;
   - overige generale: 4,5 uur vóór aanvang tot één uur na afloop.
4. Neem de vroegste vereiste start en de laatste vereiste eindtijd van de dag.
5. Bereken de basisdienst:
   - past alles binnen 09:00-17:00, gebruik dan 09:00-17:00;
   - is het verplichte venster langer dan acht uur, behoud dat hele venster;
   - anders verschuif een achtuursblok zodat het verplichte venster past;
   - regels met `preserve_required_window` behouden eerst hun exacte venster.

   Zonder de speciale regels en afronding ziet de kern van die berekening er
   bijvoorbeeld zo uit:

   ```python
   from datetime import datetime, time, timedelta

   target = timedelta(hours=8)
   day_start = datetime.combine(day, time(9, 0))
   day_end = datetime.combine(day, time(17, 0))

   if day_start <= required_start and required_end <= day_end:
       shift_start, shift_end = day_start, day_end
   elif required_end - required_start > target:
       shift_start, shift_end = required_start, required_end
   else:
       shift_start = max(
           required_end - target,
           min(day_start, required_start),
       )
       shift_end = shift_start + target
   ```

   Dit is alleen de basis. Een speciale showregel kan een ander venster
   kiezen. Daarna volgen de afronding en rustcontrole.
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

### 7. Een CAO-conflict proberen op te lossen met TEAM-AVM

Heeft een dienst van AVM1 of AVM2 een CAO-conflict, dan probeert de planner
events naar TEAM-AVM te verplaatsen. Dat gebeurt maximaal 500 keer:

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

### 8. Controleren en uitvoer schrijven

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
Generale repetities beginnen 4,5 uur vóór aanvang en eindigen één uur na de
werkelijke eindtijd. Een generale met aanvang 14:00 begint om 10:00.
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
