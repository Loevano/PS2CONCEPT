# Offline Auto Planner

Auto Planner zet een productieplanning van NO&B uit een PDF om in een
conceptrooster voor AVM. Alles gebeurt lokaal. De planner wijzigt de PDF niet
en schrijft niet rechtstreeks naar het definitieve Excel-rooster.

De uitvoer is altijd een voorstel. Controleer deze voordat je gegevens
overneemt.

## Eenmalige installatie

Voer dit uit vanuit de hoofdmap van Auto Planner:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

Daarna zijn voor normaal gebruik alleen `./add` en `./generate` nodig.

## Een productie plannen

### 1. Maak de productiemappen

Gebruik het seizoen en een korte productienaam:

```bash
./add 2627 cinderella
```

Dit maakt de volgende mappen en bestanden:

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

### 2. Voeg de planning toe

Plaats een of meer plannings-PDF's in:

```text
producties/2627/cinderella/input/
```

Als hier meerdere PDF's staan, gebruikt de planner het bestand dat het laatst
is aangemaakt of gewijzigd.

### 3. Maak het conceptrooster

```bash
./generate cinderella
```

Bestaat dezelfde productienaam in meerdere seizoenen, voeg dan het seizoen toe:

```bash
./generate 2627-cinderella
```

Je kunt dit commando veilig opnieuw uitvoeren. De planner vervangt dan de
eerder gemaakte bestanden in `output/`.

### 4. Beantwoord eventuele vragen

Als noodzakelijke informatie ontbreekt, maakt de planner dit bestand:

```text
answers/decisions.json
```

Vul de antwoorden in en voer hetzelfde `generate`-commando opnieuw uit.

## Uitvoer

De resultaten staan in de map `output/`:

| Bestand | Inhoud |
|---|---|
| `concept-rooster.csv` | Eén regel per voorgestelde AVM-dienst; geschikt voor controle en overname naar Excel |
| `concept-rooster.txt` | Leesbaar dagoverzicht van het conceptrooster |
| `events.txt` | Beoordeling van alle activiteiten uit de bronplanning |
| `issues.txt` | Ontbrekende invoer, conflicten, waarschuwingen en punten die handmatig moeten worden gecontroleerd |
| `controle.json` | Volledige technische uitvoer, inclusief verwijzingen naar de bronregels |

De productie krijgt een van deze statussen:

| Status | Betekenis |
|---|---|
| `invoer_nodig` | Noodzakelijke informatie ontbreekt of een verplichte activiteit is niet volledig ingepland |
| `concept_met_conflicten` | Er zijn bekende conflicten, waarschuwingen of onduidelijke activiteiten |
| `concept` | De planner heeft geen concreet probleem gevonden; handmatige controle blijft nodig |

Een conflict voorkomt het maken van de uitvoer niet.

## Begrippen

- Een **activiteit** komt uit de bronplanning, bijvoorbeeld een repetitie of
  voorstelling.
- Een **dienst** is de voorgestelde werktijd van één AVM'er op één dag.
- **AVM1** en **AVM2** zijn de twee vaste AVM-posities in het conceptrooster.
- **TEAM-AVM** is een extra positie die de planner alleen inzet om een
  conflict met dienstduur of rust op te lossen.
- **Overstaan** betekent dat de afsluitregel `Afsluiten` of `Afsluiting` in de
  bronplanning staat.

## Welke activiteiten worden beoordeeld?

De planner herkent vaste Nederlandse en Engelse termen uit de
productieplanning.

De normale AVM-periode begint op de dag van de eerste activiteit op het
Hoofdtoneel. De volgende activiteiten kunnen al vóór die dag worden
ingepland:

- proefbouw;
- ontwerpteamoverleg (OT);
- presentatie van cast en huis;
- de grote studiorepetitie van DNO;
- voorbereiden voor belichten;
- oplevering van het decor;
- werk in de Montagehal.

De planner neemt deze activiteiten niet op in het AVM-rooster:

- activiteiten in de Operastudio's en Het Concertgebouw;
- technische tijd;
- licht richten;
- reguliere HNB-balletrepetities;
- repetities in een studio of de Grote Studio.

De benoemde uitzonderingen, zoals de grote studiorepetitie van DNO en
specifieke HNB-repetities, worden wel volgens hun eigen regels beoordeeld.

Termen zoals `video`, `geluid` en `soundcheck` zijn niet eenduidig genoeg. De
planner zet deze in `issues.txt` voor handmatige controle. Dat gebeurt ook met
losse AVM-notities die niet betrouwbaar aan één activiteit kunnen worden
gekoppeld.

Een eindtijd na middernacht wordt op de volgende kalenderdag gezet.

## Bezetting en aanwezigheid

Onderstaande tabel bevat de belangrijkste actieve regels. Tenzij een
afwijkende tijd staat vermeld, rekent de planner met aanwezigheid vanaf één
uur vóór tot één uur na de activiteit. Bij overstaan wordt iedere genoemde
uitloop van één uur verkort naar 30 minuten.

| Activiteit | Bezetting | Aanwezigheid |
|---|---|---|
| Voorstelling of schoolvoorstelling | AVM1 en AVM2 | 120 min vooraf, 60 min na afloop*|
| Generale repetitie | AVM1 en AVM2 | 4,5 uur vooraf, 60 min na afloop*|
| Voorgenerale orkest (VGO) of pianovoorgenerale (PVG) | AVM1 en AVM2 | 120 min vooraf, 60 min na afloop*|
| Orkesttoneelrepetitie (OTR) of zit-/sitzprobe (ZIT) | AVM1 en AVM2 | 120 min vooraf, 60 min na afloop*|
| Orkestrepetitie op het Hoofdtoneel | AVM1 en AVM2 | 60 min vooraf, 60 min na afloop*|
| Regierepetitie op het Hoofdtoneel | AVM1 en AVM2 | 120 min vooraf, 60 min na afloop*|
| Technische repetitie | Eén AVM'er, bij voorkeur AVM1 | 60 min vooraf, 60 min na afloop*|
| Pianotoneelrepetitie | AVM1 en AVM2 | 60 min vooraf, 30 min na afloop |
| Solistenrepetitie | AVM1 en AVM2 | 30 min vooraf, 30 min na afloop |
| Cd-toneelrepetitie | Eén van beide AVM'ers | 60 min vooraf, 30 min na afloop |
| Belichten | Precies één van beide AVM'ers | 30 min vooraf, 30 min na afloop |
| Piano-cd | AVM1 en AVM2 | 60 min vooraf, 30 min na afloop |
| Proefbouw | AVM1 | Alleen tijdens de activiteit |
| Ontwerpteamoverleg (OT) | AVM1 | Alleen tijdens de activiteit; verhindering handmatig controleren |

Lunch en diner tellen niet mee als gewerkte voorbereidingstijd. Een
schoolvoorstelling om 13:30 met een lunchpauze in de voorbereiding krijgt
daarom een oproeptijd van 11:00.

Voor enkele situaties gelden aparte diensttijden:

- Een generale om 14:00 begint om 10:00 en eindigt 60 minuten na de werkelijke
  eindtijd, of 30 minuten erna bij overstaan.
- Bij één zondagvoorstelling om 14:00 is de dienst normaal 10:00-18:00, maar
  bij overstaan eindigt de dienst 30 minuten na de voorstelling. De regel geldt
  alleen als de benodigde tijd na afloop volledig binnen de dienst past.
- Deze zondagregel geldt niet bij twee voorstellingen op dezelfde dag.
- Een berekende dienststart om precies 12:00 wordt 11:30. Deze correctie
  vervalt als de dienst daardoor langer dan 13,5 uur wordt.

Bij twee voorstellingen op één dag blijven AVM1 en AVM2 voor beide
voorstellingen ingepland. Als de normale dienst langer dan 13,5 uur zou worden,
behoudt de planner de laatste 13,5 uur. Daardoor kan voorbereiding vóór de
eerste voorstelling vervallen; controleer die situatie altijd handmatig.

## DNO-afspraken

- De presentatie van cast en huis wordt door AVM1 gedaan.
- De grote DNO-studiorepetitie wordt door AVM1 gedaan.
- Voorbereiden voor belichten wordt alleen op de eerste bijbehorende dag op
  het Hoofdtoneel ingepland. Normaal is dit een gebruikelijk moment voor AVM1.
- Als decorinbouw is bevestigd, zijn AVM1 en AVM2 verplicht bij die
  voorbereiding.
- Decorinbouw in de Montagehal wordt door AVM1 gedaan.
- Oplevering van het decor wordt met één beschikbare AVM'er ingepland als dit
  zonder CAO-conflict mogelijk is.
- Proefbouw, ontwerpteamoverleg, presentaties, decorinbouw en oplevering krijgen
  geen extra voorbereidings- of afbouwtijd.

Voor DNO vraagt de planner of decorinbouw nodig is. Een antwoord ziet er
bijvoorbeeld zo uit:

```json
{
  "decor_inbouw_nodig": {
    "value": "ja",
    "day": "2026-09-14",
    "start": "09:00",
    "end": "12:00"
  }
}
```

Staat al een passend moment in de bronplanning, dan zijn datum en tijd in het
antwoord niet nodig. Bij `ja` zonder bestaand moment of volledige tijdgegevens
blijft de status `invoer_nodig`.

## Diensten en CAO-controle

De planner streeft naar diensten van acht uur:

- Activiteiten die volledig binnen 09:00-17:00 passen, krijgen normaal die
  standaarddienst.
- Andere diensten worden verschoven zodat de benodigde aanwezigheid past.
- Begin- en eindtijden worden naar buiten afgerond op halve uren.
- Een korte dienst wordt waar mogelijk verlengd tot acht uur, zonder vóór
  09:00 te beginnen. Een verplichte eerdere oproeptijd blijft wel staan.
- Een dienst duurt maximaal 13,5 uur.
- Tussen twee diensten blijft minimaal elf uur rust.

De dagafsluiting bepaalt de benodigde tijd na de laatste AVM-activiteit. Bij
overstaan worden alle regels met 60 minuten uitloop verkort naar 30 minuten:

| Tekst in bronplanning | Betekenis | Tijd na laatste AVM-activiteit |
|---|---|---:|
| `Afsluiten` of `Afsluiting` | Overstaan | 30 minuten |
| `Afbouw` | Niet overstaan | 60 minuten |

Bij een conflict probeert de planner eerst daarvoor geschikte activiteiten
naar TEAM-AVM te verplaatsen. Piano-cd, belichten en cd-toneelrepetitie komen
daarvoor als eerste in aanmerking. Proefbouw, ontwerpteamoverleg en de
DNO-presentatie van cast en huis blijven altijd bij de vaste AVM-posities. Bij
een voorstelling blijft minimaal één van de vaste AVM-posities aanwezig.

De CAO-controle is gedeeltelijk. De planner controleert alleen:

- de duur van een dienst;
- de rust tussen opeenvolgende diensten.

Week- en vierwekentotalen kunnen pas worden gecontroleerd met volledige
persoonlijke roosters.

## Planniveaus

Niet iedere afspraak is even bindend:

| Niveau | Betekenis |
|---|---|
| Verplicht | Moet volledig worden ingepland |
| Richtlijn | Inplannen als dit zonder CAO-conflict kan |
| Gebruikelijk | Normaal voorstellen, maar eerder weglaten dan een richtlijn |
| Optioneel | Alleen toevoegen als dit binnen een bestaande dienst past |

Een open productievraag is geen prioriteit. Het antwoord bepaalt alleen of een
regel wel of niet geldt.

## Regels aanpassen en testen

De actieve AVM-regels staan in
[`config/avm_rules.json`](config/avm_rules.json). De vastgelegde CAO-bronnen en
regels staan in [`config/cao_rules.json`](config/cao_rules.json).

Voer alle tests uit met:

```bash
.venv/bin/python -m unittest discover -s tests -v
```
