# JHKBot

Egyszerű Discord bot Pythonban, amivel reakciók alapján lehet role-okat adni és elvenni.

- Reakció hozzáadása → a hozzá tartozó role megkapása
- Reakció eltávolítása → a role levétele
- Unicode és custom emoji-k támogatása
- Több Discord szerveren is használható
- A beállítások config.json-ban vannak
- A bot tokenje .env-ben van
- Nem használ adatbázist

## Követelmények

- Python 3.11+
- Discord bot a Developer Portalon
- A botnak Manage Roles és View Channel jogosultság kell

## Beállítás

### 1. Discord bot létrehozása

A Discord Developer Portalon hozz létre egy új alkalmazást, majd a Bot menüpontban:

- másold ki a bot tokenjét,
- kapcsold be a Message Content Intentet,
- a többi Privileged Intent nem szükséges.

A botot hívd meg a szerveredre legalább ezekkel a jogokkal:

- Manage Roles
- View Channels
- Read Message History

Az Administrator jogosultság nem szükséges.

Fontos, hogy a bot saját role-ja legyen magasabban, mint azok a role-ok, amelyeket kiosztani szeretnél.

### 2. Telepítés

```powershell
git clone https://github.com/doomhyena/JHKBot.git
cd JHKBot
```

Virtuális környezet létrehozása:

**Windows:**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Függőségek telepítése:

```bash
pip install -r requirements.txt
```

### 3. Token beállítása

Másold le az .env.example fájlt .env néven:

```bash
cp .env.example .env
```

Windows alatt:

```powershell
copy .env.example .env
```

Majd írd bele a bot tokenjét:

```env
DISCORD_TOKEN=a_te_tokened
BOT_PREFIX=!
```

## Konfiguráció

### Környezeti változók (.env)

| Változó         | Kötelező | Alapérték     | Leírás                                                                   |
|-----------------|----------|---------------|--------------------------------------------------------------------------|
| `DISCORD_TOKEN` | igen     | –             | A bot tokenje a Developer Portalról.                                     |
| `BOT_PREFIX`    | nem      | `!`           | A prefix parancsok előtagja (pl. `!help`, `?help`).                       |
| `CONFIG_PATH`   | nem      | `config.json` | A reaction role konfigurációs fájl elérési útja (a `bot.py` mappájához képest). |
| `ALLOWED_USER_IDS` | igen  | –             | Vesszővel elválasztott Discord user ID-k, akik a `reaction-role` parancsokat használhatják. |

- Ha a `DISCORD_TOKEN` hiányzik, a bot el sem indul, és hibát ír a konzolra.
- Ha a `BOT_PREFIX` üres vagy hiányzik, a bot figyelmeztet, és a `!` prefixet használja.
- A súgó (`help`) és a hibaüzenetek mindig a beállított prefixet mutatják.

### config.json

A reaction role-ok beállításai a `config.json` fájlban vannak. Egy szerver esetén ez a legegyszerűbb forma:

```json
{
    "guild_id": 123456789012345678,
    "messages": {
        "234567890123456789": {
            "description": "Játékfejlesztői szerepkörök",
            "roles": {
                "🎮": 345678901234567890,
                "<:valami:456789012345678901>": 567890123456789012
            }
        }
    }
}
```

Több szerverhez a `guilds` formát használd, ahol a kulcs a szerver ID-ja:

```json
{
    "guilds": {
        "123456789012345678": {
            "messages": {
                "234567890123456789": {
                    "description": "Szerepkörök",
                    "roles": {
                        "🎮": 345678901234567890
                    }
                }
            }
        }
    }
}
```

Mezők:

- `guild_id` / `guilds` kulcsa: a Discord szerver ID-ja.
- `messages`: az üzenet ID → beállítás párok. Az üzenet a szerver bármelyik szöveges csatornájában lehet, amit a bot lát.
- `description`: szabad szöveges leírás (nem kötelező).
- `roles`: emoji → role ID párok. Üzenetenként legalább egy kell, és egy emoji csak egyszer szerepelhet.

Szabályok:

- Az ID-k 15–20 számjegyű egész számok (számként vagy szövegként is megadhatók).
- Emoji lehet Unicode (pl. `🎮`) vagy custom (`<:nev:id>`). A `:shortcode:` forma (pl. `:video_game:`) nem működik.
- A fájlt a bot induláskor ellenőrzi. Hibás JSON vagy érvénytelen érték esetén nem indul el, és megírja, melyik mezővel van gond.
- Induláskor a bot minden konfigurált üzenetre kiteszi a hozzá tartozó reakciókat.
- Ha a `/reaction-role add` vagy `remove` parancsot használod, a bot maga írja felül a `config.json`-t, mindig a `guilds` formában.

Az ID-k kimásolásához Discordban kapcsold be a Fejlesztői módot, majd jobb klikk az adott szerveren, üzeneten vagy role-on → ID másolása.

Custom emoji is használható, például:

```text
<:valami:123456789012345678>
```

A bot az emoji és a role ID-ja alapján dolgozik, így egy role átnevezése nem okoz problémát.

## Beállítás Discordból

A bot slash parancsokat is biztosít.

Például:

```text
/reaction-role add
```

vagy prefixszel (a `!` helyett a `BOT_PREFIX`-ben megadott előtagot használd):

```text
!reaction-role add <üzenet_id> @Role 🎮
```

Ezzel hozzáadhatsz egy emoji → role párost egy meglévő üzenethez.

További hasznos parancsok:

```text
/reaction-role remove
/reaction-role reload
```

| Parancs                                                   | Leírás                                                        |
|-----------------------------------------------------------|---------------------------------------------------------------|
| `/help`, `!help`                                          | Súgó megjelenítése.                                           |
| `/reaction-role add message_id role emoji [description]`  | Emoji → role páros hozzáadása, mentés és reakció kitétele.    |
| `/reaction-role remove message_id emoji`                  | Emoji → role páros törlése.                                   |
| `/reaction-role reload`                                   | A `config.json` újraolvasása újraindítás nélkül.              |

A `reaction-role` parancsokat csak az `ALLOWED_USER_IDS`-ben megadott felhasználók használhatják, bármelyik csatornában. A célüzenet is lehet bármelyik csatornában (szöveges, hang-, stage csatorna chatje, thread, fórumposzt), amit a bot lát.

## Indítás

A virtuális környezet aktiválása után:

```bash
python bot.py
```

Ha minden rendben van, a bot bejelentkezik és elkezdi figyelni a konfigurált üzeneteket.

Leállítás:

```text
Ctrl + C
```

## Fontos

A bot csak olyan role-t tud kiosztani, amely alatta van a bot legmagasabb role-jának.

Ha nem működik a reakció:

- Ellenőrizd az üzenet és a role ID-ját.
- Nézd meg, hogy a bot látja-e az adott csatornát.
- Ellenőrizd a Manage Roles jogosultságot.
- Ellenőrizd a role-hierarchiát.

A config.json kézi módosítása után indítsd újra a botot, vagy futtasd a `/reaction-role reload` parancsot. A `.env` módosításához újraindítás kell.

A bot újraindítás után is működik a korábban beállított üzeneteken. A leállás alatt történt reakcióváltozásokat viszont nem pótolja visszamenőleg.

## Projektstruktúra

```text
reaction-role-bot/
├── bot.py
├── config.json
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── utils/
    ├── __init__.py
    ├── config.py
    └── emoji.py
```